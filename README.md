# MediaFlow

MediaFlow is a user-experience-first media organizer with strong, transparent safety and
data-integrity guarantees. It provides Storage adapters for Local, SMB, OpenList, AWS S3,
Cloudflare R2, and generic S3-compatible services. Its production pipeline scans media, parses
filenames, recognizes a configured type,
identifies metadata, calculates names and classification, plans an operation, and optionally
executes it. Dry-run is always the default.

Local parsing accepts filename/path evidence and optional same-directory Kodi/Jellyfin-style NFO
evidence through a bounded, read-only Storage flow. NFO parsing never generates files or creates a
metadata identity by itself.

The core workflow has a bounded production-release profile. Production adapters passed isolated
Local, Samba, OpenList, and MinIO lifecycle/transfer matrices plus a
128-object, 128 MiB streaming and interrupted-transfer profile. This does not certify AWS S3,
Cloudflare R2, third-party OpenList drivers, remote atomic publication, multi-hour soak, or host
power-loss behavior. Fake-client tests are never counted as real-service evidence. See the
[Storage Acceptance Matrix](docs/storage-acceptance.md).

Real acceptance suites are destructive only inside explicitly named `mediaflow-acceptance-*` roots
and require a fixed confirmation value. They have no default test root and never derive consent from
runtime or user configuration. Each suite proves its root is empty before mutation and writes a new
non-secret JSON evidence record; see the matrix document for exact boundaries and results.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev,tmdb]'
cp config/strategy.example.json config/mediaflow.json
```

Edit Storage and library roots in `config/mediaflow.json`. `ResourceLibrary.storagePath` and
`MediaLibrary.rootPath` are paths relative to their referenced Storage root. Optional
`ResourceLibrary.displayRootPath` binds legacy positional paths; no-path scanning does not need it.
Provider secrets remain environment variables:

```bash
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
export TMDB_ACCESS_TOKEN="<token>"
export MEDIAFLOW_API_TOKEN="<long-random-development-token>"
export MEDIAFLOW_WEBHOOK_SECRET="<independent-random-webhook-secret>"
```

## V1 self-hosted release status

V1 `1.0.0` is released at `v1.0.0` and maintained on `release/v1`. Production self-hosting uses
one Docker image, four Compose services and Waitress-backed `api serve-production`; the standard-
library listener remains for trusted-loopback development. Fresh setup supports a management-only
bootstrap and Web-created managed configuration.

See [release boundaries and validation](docs/release.md) and [deployment](docs/deployment.md).

## V2 development status

`main` is the V2 development trunk (`2.0.0.dev0`) for Operator Web Architecture & UX Modernization.
V2 is not yet a released product line. The Python `/api/v1/*` authority and V1 `/ui` remain available.
Slice 44's accepted improvements cover ordinary maintenance on both library kinds, Rules forms
and family-local tests with a separate complete-flow check, MediaLibrary-plus-path classification
with explicit legacy conversion, long-name navigation/toolbars, and bounded ResourceLibrary
folder/mixed organization through exact Preview and separate execution confirmation. Exceptional
discovery interruption can safely stop with explicit new discovery; seamless recovery for every
crash/control/activation combination remains deferred. Slice 43 remains user-frozen.

[Roadmap](docs/roadmap.md) owns large-Slice priority/status; [Progress](docs/progress.md) records
accepted closures and their Base/Head. [SLICE.md](SLICE.md) and [TASK.md](TASK.md) own current
scope, implementation/review state and next actions.

## V2 frontend (web/)

`web/` is a React + TypeScript + Vite SPA using TanStack Router and TanStack Query. Python serves
the built artifact at `/ui-v2/`; Node is build/development tooling only. The browser holds the API
principal token in memory and uses shared backend permissions and application behavior.

See [frontend architecture and ownership](docs/architecture.md#v2-program-architecture),
[current operator journeys](docs/product-experience.md) and
[production artifact serving](docs/deployment.md#v2-frontend-artifact-and-serving).

Development and verification commands (run after the repository Setup):

```bash
npm --prefix web ci            # install the pinned toolchain from the lockfile
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run   # Vitest + React Testing Library
npm --prefix web run build     # deterministic static artifact into web/dist
npm --prefix web run test:e2e  # minimal Playwright path against web/dist + a local fake API
```

`npm --prefix web run test:e2e` requires the Playwright Chromium browser
(`npx --prefix web playwright install chromium` plus system dependencies when needed); it uses
local fake tokens and a local fake API only.

`docker compose build` builds the frontend from the pinned lockfile and ships only its static
artifact in the Python runtime image. See [deployment](docs/deployment.md) for packaging and startup.

## CLI

### Slice45 target: live file lists

The active Slice45 Contract selects shared live Storage browsing for CLI, Files and MediaLibrary.
These target commands are pending implementation; each lists one configured library directory
without creating FileIndex, Task, Result or discovery records:

```bash
mediaflow files list --resource-library source --path "incoming" --limit 100
mediaflow files list --media-library media --path "Movies" --limit 100
```

Choose exactly one library; omit `--path` to list its root and use the returned `--cursor` for the
next page. Global catalog filters and file-ID detail/statistics remain outside this live-list target.
The service has not launched, so this work does not provide old FileIndex production-data migration
or history compatibility. See [the FileIndex retirement target](docs/file-index-retirement-spec.md).
Task/Result/audit and source-safety persistence for explicit work remain required.

The active Slice45 Contract treats the service as a first deployment: there is no standalone Scan
workflow or scan-only/scan-and-plan Automation mode. Shared discovery/filtering/real stability and
planning remain part of supported Preview and organization workflows. Unknown old routes and commands
use ordinary not-found/argument errors; no old Scan/V1 compatibility is provided.

### Baseline command reference

The examples below describe currently supported command-line workflows.

```bash
mediaflow analyze "/path/to/movie.mkv"
mediaflow analyze --offline "/path/to/movie.mkv"
mediaflow config validate
mediaflow config status
mediaflow config draft-import
mediaflow config draft-validate REVISION_ID
mediaflow config activate REVISION_ID --expected-version VERSION
mediaflow dashboard --recent-limit 10
mediaflow files list --limit 100
mediaflow files list --after 2026-08-23T12:00:00+00:00 --cursor-file-id FILE_ID --limit 100
mediaflow files list --recognition-type C --provider-id 101 --title Matrix --year 1999 --limit 100
mediaflow files show FILE_ID
mediaflow metadata-reviews list --limit 100
mediaflow recognition-reviews list --limit 100
mediaflow recognition-reviews show REVIEW_ID
mediaflow recognition-reviews resolve REVIEW_ID --recognition-type C --actor operator
mediaflow recognition-reviews resolve-pending --recognition-type C --actor operator --limit 100
mediaflow metadata-reviews show REVIEW_ID
mediaflow metadata-reviews resolve REVIEW_ID --candidate-rank 1
mediaflow metadata-reviews resolve-pending --candidate-rank 1 --actor operator --limit 100
mediaflow metadata-corrections list --limit 100
mediaflow metadata-corrections show REVIEW_ID
mediaflow metadata-corrections resolve REVIEW_ID --query "Correct title" --year 2025 --media-type movie --actor operator
mediaflow metadata-corrections resolve REVIEW_ID --provider-id 858024 --media-type movie --actor operator
mediaflow metadata-corrections resolve-pending --query "Correct title" --media-type movie --actor operator --limit 100
mediaflow tasks ignore-item TASK_ID ITEM_ID --actor operator --note "not managed"
mediaflow tasks ignore-pending --actor operator --note "not managed" --limit 100
mediaflow tasks ignore-pending --task-id TASK_ID --actor operator --limit 20
mediaflow classification-reviews list --limit 100
mediaflow classification-reviews show REVIEW_ID
mediaflow classification-reviews resolve REVIEW_ID --choice-rank 1
mediaflow preview --limit 20
mediaflow organize --limit 20
mediaflow organize --execute --limit 20
mediaflow tasks list
mediaflow confirmations list
mediaflow confirmations show CONFIRMATION_ID
mediaflow confirmations resolve CONFIRMATION_ID --strategy skip
mediaflow storage list
mediaflow storage check
mediaflow storage check STORAGE_ID
mediaflow tasks show TASK_ID
mediaflow tasks pause TASK_ID
mediaflow tasks resume TASK_ID
mediaflow tasks retry-failed TASK_ID --execute
mediaflow jobs submit preview --limit 20
mediaflow jobs list
mediaflow worker run-next
mediaflow worker run
mediaflow scheduler list
mediaflow scheduler tick
mediaflow scheduler run
mediaflow scheduler audit
mediaflow scheduler audit SCHEDULE_ID --limit 100
mediaflow notifications list --limit 100
mediaflow notifications list --status dead-letter
mediaflow notifications stale --age-seconds 300
mediaflow notifications requeue DELIVERY_ID
mediaflow notification-worker run-next
mediaflow notification-worker run
mediaflow execution-authorizations issue --ttl-seconds 300 --max-items 20
mediaflow execution-authorizations list
mediaflow execution-authorizations show AUTHORIZATION_ID
mediaflow execution-authorizations revoke AUTHORIZATION_ID
mediaflow security-audit list --limit 100
mediaflow api serve --host 127.0.0.1 --port 8787
```

The retired direct file re-recognition, metadata re-match, file re-plan and recognition-review retry
commands are no longer exposed by the current CLI, Web UI or `/api/v1` surface. Use the supported
review resolution, metadata continuation, and explicit Task retry/recovery flows instead.

`preview` and `organize` without `--execute` produce DryRun results. Only `organize --execute`
permits Storage mutations. Existing destinations enter the configured Skip/Rename/Manual/Overwrite
decision flow. Overwrite is rejected unless the OrganizePolicy enables it and the user records a
fresh `--confirm-overwrite` decision; unresolved conflicts remain non-mutating.
Silent deletion is not enabled.

Read-only workflow retry is optional and disabled by default. Configure `workflowRetry` with
`enabled`, `maxAttempts` (1–10), `baseDelaySeconds`, `maxDelaySeconds` (at most 300), and
`jitterRatio` (0–1). It applies only to normalized timeout, connection, rate-limit, and temporary
provider-unavailable failures before planning/execution. It never retries OrganizerExecutor
mutations or uncertain outcomes, and enabling it does not grant `--execute` authority.

OrganizePolicy may optionally compare an existing destination with `none`, bounded `fast`, or
streaming `full` Hash evidence. The default is `none` and performs zero Hash reads. FAST is explicitly
prefix evidence rather than full-content certainty; any configured calculation failure blocks as an
unknown conflict and never authorizes overwrite or deletion.

Attachment handling is opt-in per OrganizePolicy. When enabled, MediaFlow lists only the primary
file's directory through Storage and groups matching subtitles, NFO, artwork, images, and trailers
into the same plan. Preview reports `attachments=N`; only explicit execution mutates them. Unknown
files are never included or cleaned up.

Source directory cleanup is opt-in per OrganizePolicy and defaults to `none`. `empty` removes only
verified empty ancestors after a fully successful MOVE. `ignorable` additionally permits only
explicit basename patterns such as `.DS_Store`; unknown files, links, subdirectories, entry limits,
boundary changes, COPY/LINK, DryRun, failed/partial execution and rollback all prevent cleanup.
The configured ResourceLibrary `storagePath` is an exclusive boundary and is never deleted.

With no path argument, `preview` and `organize` iterate every enabled configured ResourceLibrary.

The portable plan retains both Storage identities, for example source
`source-storage:Media/电影/Movie.mkv` and destination
`target-storage:Movies/外语电影/Movie/Movie.mkv`. Local↔Local, Local↔OpenList, and
OpenList↔OpenList use the same pipeline. A same-OpenList MOVE that changes both directory and
filename uses native server-side Move followed by Rename; it does not download/upload the media.
Cross-storage MOVE streams Copy, verifies the destination, and only then deletes the source.

The developer strategy inspector remains available as `strategy-test`.

`config draft-import` stages the bootstrap JSON as a managed Draft. After checked activation,
the immutable managed revision is runtime authority; new work pins it and failures remain fail-closed.
See the [configuration guide](docs/configuration.md) for forms-first management, page-local library
Save, exact-revision tests/previews, secret-free exchange and activation/recovery. Configuration
changes and analysis grant no media execution authority.

## Development workflow

Read [AGENTS.md](AGENTS.md) and [the development workflow](docs/development-workflow.md) before
work. [SLICE.md](SLICE.md) owns the current capability contract; [TASK.md](TASK.md) owns the active
implementation unit, planned from [the Task template](Task/TEMPLATE.md).

- **A:** owns Slice scope, architecture and final review; read [A experience](docs/agent-experience/slice-owner-architect-final-reviewer.md).
- **B:** plans/reviews Tasks and runs full regression and acceptance; read [B experience](docs/agent-experience/task-planner-reviewer.md).
- **Developer:** implements the active Task and runs new/changed/directly affected tests; read [Developer experience](docs/agent-experience/developer-implementation-role.md).

At each Slice closure, merge only new reusable lessons into these short lists in the same closure
checkpoint. Add nothing when there is no new reusable lesson; detailed Task history stays in Git.

## Configuration and architecture

- [Runtime configuration](docs/configuration.md)
- [Architecture](docs/architecture.md)
- [Canonical product requirements and stable IDs](docs/requirements.md)
- [V2 requirements](docs/v2-requirements.md)
- [Large-Slice roadmap](docs/roadmap.md)
- [Slice closure ledger](docs/progress.md)

Operation history is appended as JSON Lines at the configured `historyPath`.
`MEDIAFLOW_CONFIG` supplies the compatibility bootstrap; activated managed snapshots own runtime
strategy. Use `config/strategy.example.json` for the A/B/C example and validate before processing.

For OpenList, install the optional dependency and keep its token outside JSON:

```bash
.venv/bin/pip install -e '.[openlist,tmdb]'
export OPENLIST_TOKEN='<token>'
```

SMB and S3/R2 runtime adapters also use environment-owned credentials:

```bash
.venv/bin/pip install -e '.[smb,s3]'
export SMB_USERNAME='<username>'
export SMB_PASSWORD='<password>'
export S3_ACCESS_KEY='<access-key>'
export S3_SECRET_KEY='<secret-key>'
mediaflow storage list
mediaflow storage check
```

`storage list` never constructs adapters. `storage check` performs only health/list operations and
never writes to Storage.

## Development API and DryRun worker

The local development WSGI API uses configuration-driven principals. Credentials remain in the
environment; JSON contains only their environment-variable names and least-privilege roles:

```json
"api": {
  "principals": [
    {"id": "local-admin", "tokenEnv": "MEDIAFLOW_API_TOKEN",
     "roles": ["admin"], "enabled": true}
  ]
}
```

`GET /health` is public. Every `/api/v1` request requires
`Authorization: Bearer $MEDIAFLOW_API_TOKEN`. Roles are `viewer`, `operator`, `executor`,
`auditor`, and `admin`; executor permission is necessary but not sufficient for real organization.
The API can query tasks, jobs, and pending confirmations, and it accepts bounded `preview` and
`organize` Job submissions. Run one queued item with `mediaflow worker run-next`; Preview is
always DryRun/zero-mutation. Organize is accepted only through the separate
disabled-by-default one-time authorization boundary documented below. Remote overwrite, delete, and
conflict resolution remain rejected. This standard-library server is for trusted loopback
development use, not direct Internet exposure.

MediaFlow provides a resident Worker and opt-in interval schedules. Example schedules are disabled
by default. `automation.maximumActiveJobs` defaults to 100 and atomically limits the combined Pending
and Running backlog across manual DryRun submissions, schedules, and protected remote organize.
Completed, failed, and cancelled Jobs release capacity. Run Scheduler and Worker separately.
`automation.staleJobAgeSeconds` defaults to 3600 (allowed range 60–604800). The authenticated Jobs
page can explicitly list at most 100 Running Jobs older than this threshold. This is read-only
diagnostic evidence, not proof that a worker died; execute-authorized organize Jobs require manual
investigation and are never automatically recovered.
`jobs cancel JOB_ID` cancels pending work immediately
or requests cooperative cancellation of running work before another media item starts; an in-flight
read may finish. Stale crash leftovers are never retried automatically: inspect with
`jobs stale --age-seconds N` and explicitly use `jobs requeue JOB_ID --age-seconds N`.
Running Workers now hold an opaque persisted fenced claim and refresh `updated_at` at cooperative
workflow boundaries. Requeue clears that claim, and an old Worker cannot heartbeat or commit over a
later claim. The signal remains conservative during a blocking external call, so operators must
still stop and inspect the owning Worker and Storage outcome before local requeue. Automatic and
remote recovery remain unavailable.

The Scheduler supports a validated five-field Cron subset with an explicit IANA time zone:

```json
{"id": "cn-morning-preview", "command": "preview", "cron": "0 8 * * *",
 "timezone": "Asia/Shanghai", "limit": 20, "enabled": false}
```

Cron supports numeric `*`, lists, inclusive ranges, and positive steps. It has no seconds, names,
macros, shell commands, or catch-up backlog. Nonexistent DST wall times are skipped and an ambiguous
wall time fires once. Every emission is appended to SQLite schedule audit.

Notifications use an asynchronous Outbox for terminal Automation Job and Scheduler emission events.
Web/API manages HTTPS Webhook definitions, event selection, enable/disable state and deployment-owned
`secretEnv` references, and can send one bounded signed test pinned to the exact configuration
revision. After enabling a configured Webhook, run
`mediaflow notification-worker run`. Payloads are HMAC-SHA256 signed over
`timestamp + "." + exact UTF-8 body`; 429/5xx/transport failures retry with bounded backoff and
other 4xx responses enter dead-letter. Delivery failures never change completed media work.
Authenticated Web/API exposes bounded delivery lists and detail, automatic retry state, explicit
expired-lease recovery and dead-letter requeue. Read projections never return payload bodies or
secrets, and every recovery action is scoped to one delivery.

Claimed deliveries use the configured `deliveryLeaseSeconds` (300 by default). After a worker
crash, an expired claim is safely eligible for another attempt; its stable delivery ID lets
receivers deduplicate the unavoidable at-least-once crash window.

### Current V1 / API execution-authorization mechanism

Remote real organize Jobs currently may use a locally issued, short-lived, single-use
authorization. This capability is disabled by default and the normal API bearer token is never
sufficient mutation authority. Enable it explicitly:

```json
"api": {
  "principals": [
    {"id": "automation-executor", "tokenEnv": "MEDIAFLOW_API_TOKEN",
     "roles": ["executor"], "enabled": true}
  ],
  "remoteExecution": {"enabled": true, "maximumTtlSeconds": 900}
}
```

Issue a token locally, then submit exactly one bounded Job:

```bash
mediaflow execution-authorizations issue --ttl-seconds 300 --max-items 20
curl -X POST http://127.0.0.1:8787/api/v1/jobs \
  -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  -H "X-MediaFlow-Execution-Token: <one-time-token>" \
  -H "Content-Type: application/json" \
  --data '{"command":"organize","execute":true,"limit":20}'
mediaflow worker run-next
```

The raw authorization token is displayed once and only its SHA-256 digest is persisted. Consumption
and Job creation are atomic. Scheduler configurations remain Preview-only, and all existing
conflict/no-overwrite/OrganizerExecutor checks still apply.

For V2 interactive operation, the routine Web flow reviews an exact durable Preview and submits one
explicit confirmation without CLI issuance or raw-token copy/paste. The backend creates and
atomically consumes server-held, short-lived, single-use authority bound to the authenticated
principal, exact Preview/configuration/item set and permitted destructive effects; the resident
Worker then claims the admitted execution under its durable fence. Backend RBAC, limits, audit,
stale revalidation, no automatic uncertain replay and OrganizerExecutor-only mutation remain
mandatory. The V1 token mechanism remains available for API automation, local administration,
debugging, compatibility and emergency support.

Every authenticated or denied API request is recorded in a redacted SQLite security audit. Inspect
it locally with `mediaflow security-audit list --limit 100`, or through auditor/admin-only
`GET /api/v1/security-audit`. Audit records contain normalized routes and never contain headers,
request bodies, query strings, tokens, cookies, or exception text. The legacy single `api.tokenEnv`
form is accepted as one admin principal for compatibility, but cannot be mixed with `principals`.

The baseline read-only operational dashboard summarizes configured libraries plus persisted
FileIndex, Task, Job, confirmation, and notification state. Slice45 removes FileIndex metrics and
catalog links; it preserves Task, Result and other supported operational state.

```bash
mediaflow dashboard --recent-limit 10
curl -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  'http://127.0.0.1:8787/api/v1/dashboard?recentLimit=10'
```

It uses aggregate SQLite queries, performs no Storage health probe or provider/network request, and
redacts recent failures to identifiers, categorical status, and timestamps. Storage connectivity
remains an explicit `mediaflow storage check` operation.

Conflict confirmations also have an authenticated service workflow for future UI clients:

```bash
curl -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  'http://127.0.0.1:8787/api/v1/confirmations?status=pending&limit=20'
curl -X POST -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"strategy":"skip"}' \
  'http://127.0.0.1:8787/api/v1/confirmations/CONFIRMATION_ID/resolve'
```

Operators, executors, and admins may record remote `skip` or `rename` decisions. Viewer/auditor
roles remain read-only. Remote `manual`, `overwrite`, actor injection, destination editing, and
execute fields are rejected. A decision never resumes a Task or executes media automatically;
local explicit retry/resume remains a separate action. High-risk overwrite stays local CLI-only.

Metadata outcomes that need operator review are captured as bounded, provider-neutral snapshots:

```bash
mediaflow metadata-reviews list --limit 100
mediaflow metadata-reviews show REVIEW_ID
curl -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  'http://127.0.0.1:8787/api/v1/metadata-reviews?limit=20'
```

NeedConfirm/Ambiguous items enter `waiting_metadata` and release their source lock. Candidate
snapshots are capped at 20 and exclude overview, images, provider DTOs, credentials, and raw
HTTP/error data. Resolve only a displayed rank, then resume explicitly:

```bash
mediaflow metadata-reviews resolve REVIEW_ID --candidate-rank 1 --actor local-operator
mediaflow tasks resume TASK_ID
```

Resolution is persistence-only: it records an immutable decision and changes the waiting item to
pending, but does not contact a provider, resume a Task, create a Job, or mutate Storage. The later
explicit resume re-runs recognition/policy checks and uses the existing provider-ID details flow;
it cannot upgrade a DryRun task to execute.

An identified item for which no ClassificationRule matches enters a separate classification
review queue. Only enabled rules already present in the resolved ClassificationPolicy are offered:

```bash
mediaflow classification-reviews list --limit 100
mediaflow classification-reviews show REVIEW_ID
mediaflow classification-reviews resolve REVIEW_ID --choice-rank 1 --actor local-operator
mediaflow tasks resume TASK_ID
```

The decision cannot supply a custom MediaLibrary or path. It atomically records the configured
rule choice and makes the item pending; the later explicit resume revalidates RecognitionType,
ClassificationPolicy, rule, MediaLibrary, and safe relative path before planning. Resolution
constructs no Storage/provider and never creates or resumes a Task or Job automatically.

### Operator Web UI

Start the loopback API and open `http://127.0.0.1:8787/ui/` for V1 or `/ui-v2/` for V2 after
building the frontend. Enter a configured API principal token; it stays in page memory and the
input is cleared after connection. Reloading requires reconnecting.

The [product experience](docs/product-experience.md) describes current pages, per-role actions,
explicit decisions, cooperative controls and recovery. Web and API share application permissions
and execution rules; Preview is zero-mutation and only OrganizerExecutor mutates Storage.
Keep the development listener on trusted loopback; production serving and HTTPS/proxy boundaries
follow the [deployment guide](docs/deployment.md).

Generate and inspect API credentials without storing secret values in configuration:

```bash
mediaflow api token generate
export MEDIAFLOW_API_TOKEN='<generated value>'
mediaflow api credentials check
mediaflow logs list --limit 100 --level WARN
mediaflow logs prune
mediaflow database backup --output /safe/backups/mediaflow.sqlite3
mediaflow database verify /safe/backups/mediaflow.sqlite3
mediaflow upgrade check --backup /safe/backups/mediaflow.sqlite3
mediaflow upgrade rehearse --backup /safe/backups/mediaflow.sqlite3
mediaflow database restore /safe/backups/mediaflow.sqlite3 --confirm-empty-destination
```

The generator uses the operating-system cryptographic random source and prints the token once.

Operational logging is disabled by default. When enabled, SQLite stores only fixed event codes,
levels, components, safe task/job/plan identifiers, and status—never paths, titles, raw errors,
provider/HTTP data, arbitrary context, or credentials. `logs prune` explicitly applies configured
age and row-count retention and never touches media, Tasks, Results, history, or security audit.
The authenticated operator UI exposes the same safe fields with level-scoped Previous/Next cursors;
it cannot write or prune logs.

Backup creates a verified non-existing SQLite snapshot and never overwrites. Restore requires all
MediaFlow processes stopped, a verified backup, and a manually preserved old database/sidecars;
the destination and sidecars must be absent. Follow the [offline restore procedure](docs/release.md#offline-restore-procedure).

On POSIX, cooperating runtime commands hold a shared advisory lease and restore needs the exclusive
lease. The owner-only `.mediaflow.lock` contains no identifiers and must not be deleted while
processes may run; it does not detect unrelated programs or direct library consumers.

Before installing a new artifact, run `upgrade check` and `upgrade rehearse` against a verified
backup. Preflight checks Python/schema compatibility, integrity and a default 24-hour backup age
(explicit override: `--max-backup-age-hours 48`); rehearsal migrates only a disposable copy and
verifies representative counts. Neither changes live runtime or the backup. See
[upgrade and migration recovery](docs/deployment.md#backup-upgrade-and-migration-recovery).

## Release validation

GitHub Actions runs offline tests and quality checks on Python 3.11–3.13, then builds and installs
the wheel in isolation. See the [release checklist](docs/release.md#quality-gate) for exact commands
and artifact smoke validation. CI uses no production secrets or live media and publishes/deploys no
artifact automatically.

Credential check prints only principal ID, roles, environment-variable name, enabled state, and
SET/UNSET. For rotation, temporarily configure old and new principals with different IDs and
`tokenEnv` names, restart, migrate clients, then remove the old principal and restart again.

Non-loopback HTTP is rejected by default. A bind intended for a trusted HTTPS reverse proxy needs
explicit `--allow-insecure-remote-http`; this acknowledgement does not add encryption. Prefer
loopback binding and TLS termination at a trusted proxy.

This is a development transport statement. The production Docker path uses the explicit Waitress
WSGI serving contract; TLS termination, certificates, proxy policy and public Internet exposure
remain deployment responsibilities rather than hidden MediaFlow behavior.

## Persistent runtime state

Production preview/organize use the configured SQLite database:

```json
"persistence": {"databasePath": ".mediaflow/mediaflow.sqlite3"}
```

It stores FileIndex state, tasks, task items, normalized results, and active source locks. Config
validation does not create the database. Resume/retry creates a separately auditable task; real
mutation requires both original execute authorization and a fresh `--execute`. Existing JSONL
operation history remains compatible.

This describes the baseline schema. The [Slice45 target](docs/file-index-retirement-spec.md) removes
FileIndex tables and runtime dependencies from fresh supported deployments, while retaining
Task-scoped source observations, results, locks and audit needed for safe explicit work. Listing
alone must not initialize or migrate a runtime database. No old production FileIndex migration or
automatic deletion/rebuild of existing runtime data is part of this prelaunch change.

## Current capabilities

Current user-visible behavior and recovery are defined in the [product experience](docs/product-experience.md);
reviewed delivery and deferrals are recorded once in [Progress](docs/progress.md). Detailed guides:

| Area | Reference |
|---|---|
| Settings, Storage/library setup, organizing rules and exact Active publication | [Configuration](docs/configuration.md) |
| Files, live Storage authority, manual Organize and Task recovery | [Product experience](docs/product-experience.md) |
| Pipeline, source pins, Worker fences and execution authority | [Architecture](docs/architecture.md) |
| Runtime services, health, restart, backup and upgrades | [Deployment](docs/deployment.md) |
| Real Storage evidence and provider-specific limits | [Storage acceptance](docs/storage-acceptance.md) |

**Concurrent Local directory Delete caution.** Files Delete shows and confirms a bounded impact,
then re-reads the selected scope before `OrganizerExecutor` mutates Storage. Do not let a downloader,
sync tool, shell script or another file manager delete and recreate the same selected Local
directory while the confirmed Delete is running. In the extremely narrow interval between the last
metadata revalidation and the actual Delete, some filesystems may reuse the previous inode for a
same-name replacement, so MediaFlow may be unable to distinguish that replacement from the
confirmed directory. Before deleting an actively managed directory, pause other writers, refresh
Files, review the current impact and confirm again. If the path changed or another process may still
recreate it, stop the Delete workflow and retry only after the directory is quiescent.

Organizer rollback is an explicit per-policy option and remains disabled by default:

```json
"rollback": {"enabled": false, "cleanupCreatedDirectories": true}
```

It compensates only verified effects created by the same failed invocation. It never overwrites a
reappeared source, removes a changed target, or reverts an older execution.

Long-running Tasks support durable cooperative pause at media-item boundaries:

```bash
mediaflow tasks pause TASK_ID
mediaflow tasks resume TASK_ID
```

An in-flight item is allowed to finish; pause never interrupts OrganizerExecutor or rolls work back.
Resume creates a new auditable continuation, excludes already successful/DryRun/skipped results, and
cannot upgrade execution authority. A real organize continuation still needs a fresh `--execute`.
