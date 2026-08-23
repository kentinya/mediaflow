# MediaFlow

MediaFlow is a safety-first media organizer with Storage adapters for Local, SMB, OpenList, and
S3/R2. Its production pipeline scans media, parses filenames, recognizes a configured type,
identifies metadata, calculates names and classification, plans an operation, and optionally
executes it. Dry-run is always the default.

Local parsing accepts filename/path evidence and optional same-directory Kodi/Jellyfin-style NFO
evidence through a bounded, read-only Storage flow. NFO parsing never generates files or creates a
metadata identity by itself.

The core workflow and the bounded Phase 19 production-release profile are complete. Production
adapters passed isolated Local, Samba, OpenList, and MinIO lifecycle/transfer matrices plus a
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

## CLI

```bash
mediaflow analyze "/path/to/movie.mkv"
mediaflow analyze --offline "/path/to/movie.mkv"
mediaflow config validate
mediaflow dashboard --recent-limit 10
mediaflow metadata-reviews list --limit 100
mediaflow metadata-reviews show REVIEW_ID
mediaflow metadata-reviews resolve REVIEW_ID --candidate-rank 1
mediaflow classification-reviews list --limit 100
mediaflow classification-reviews show REVIEW_ID
mediaflow classification-reviews resolve REVIEW_ID --choice-rank 1
mediaflow scan --limit 20
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
mediaflow jobs submit scan --limit 20
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

With no path argument, `scan`, `preview`, and `organize` iterate every enabled configured
ResourceLibrary. The former path-taking preview/organize forms remain available for compatibility.

The portable plan retains both Storage identities, for example source
`source-storage:Media/电影/Movie.mkv` and destination
`target-storage:Movies/外语电影/Movie/Movie.mkv`. Local↔Local, Local↔OpenList, and
OpenList↔OpenList use the same pipeline. A same-OpenList MOVE that changes both directory and
filename uses native server-side Move followed by Rename; it does not download/upload the media.
Cross-storage MOVE streams Copy, verifies the destination, and only then deletes the source.

The developer strategy inspector remains available as `strategy-test`.

## Configuration and architecture

- [Runtime configuration](docs/configuration.md)
- [Architecture](docs/architecture.md)
- [Product requirements](影视媒体资源自动整理系统需求规格说明书.md)
- [Engineering requirements](docs/requirements.md)
- [Roadmap and current milestone](docs/roadmap.md)
- [Progress and validation](docs/progress.md)

Operation history is appended as JSON Lines at the configured `historyPath`.
All runtime strategy content is loaded from `MEDIAFLOW_CONFIG`; use
`config/strategy.example.json` as the canonical A/B/C example and run `mediaflow config validate`
before processing a library.

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
The API can query tasks, jobs, and pending confirmations, and it queues `scan` or `preview` by
default. Run one queued item with
`mediaflow worker run-next`; preview is always DryRun. Remote organize is accepted only through the
later disabled-by-default one-time authorization boundary documented below. Remote overwrite,
delete, and conflict resolution remain rejected. This standard-library server is for trusted
loopback development use, not direct Internet exposure.

Phase 18.2 adds a resident Worker and opt-in interval schedules. Example schedules are disabled by
default. `automation.maximumActiveJobs` defaults to 100 and atomically limits the combined Pending
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

Phase 18.3 supports a validated five-field Cron subset with an explicit IANA time zone:

```json
{"id": "cn-morning-preview", "command": "preview", "cron": "0 8 * * *",
 "timezone": "Asia/Shanghai", "limit": 20, "enabled": false}
```

Cron supports numeric `*`, lists, inclusive ranges, and positive steps. It has no seconds, names,
macros, shell commands, or catch-up backlog. Nonexistent DST wall times are skipped and an ambiguous
wall time fires once. Every emission is appended to SQLite schedule audit.

Phase 18.4 adds an asynchronous notification Outbox for terminal Automation Job and Scheduler
emission events. Enable a configured HTTPS Webhook, set its `secretEnv`, then run
`mediaflow notification-worker run`. Payloads are HMAC-SHA256 signed over
`timestamp + "." + exact UTF-8 body`; 429/5xx/transport failures retry with bounded backoff and
other 4xx responses enter dead-letter. Delivery failures never change completed media work.
The API exposes authenticated read-only `GET /api/v1/notifications` and never returns payload
bodies or secrets.

Claimed deliveries use the configured `deliveryLeaseSeconds` (300 by default). After a worker
crash, an expired claim is safely eligible for another attempt; its stable delivery ID lets
receivers deduplicate the unavoidable at-least-once crash window.

Phase 18.5 optionally permits a remote real organize Job through a locally issued, short-lived,
single-use authorization. It is disabled by default and the normal API bearer token is never
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
and Job creation are atomic. Scheduler configurations remain scan/preview-only, and all existing
conflict/no-overwrite/OrganizerExecutor checks still apply.

Every authenticated or denied API request is recorded in a redacted SQLite security audit. Inspect
it locally with `mediaflow security-audit list --limit 100`, or through auditor/admin-only
`GET /api/v1/security-audit`. Audit records contain normalized routes and never contain headers,
request bodies, query strings, tokens, cookies, or exception text. The legacy single `api.tokenEnv`
form is accepted as one admin principal for compatibility, but cannot be mixed with `principals`.

The read-only operational dashboard summarizes configured libraries plus persisted FileIndex,
Task, Job, confirmation, and notification state:

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

Start the existing loopback API process and open `http://127.0.0.1:8787/ui/`. The dependency-free
operator page shows the Dashboard and the conflict, metadata, and classification review queues.
It also provides read-only Task, Automation Job, Scheduler, and Notification delivery views.
Schedule occurrence audit and notification delivery pages are bounded to 1–100 rows, support stable
Previous/Next navigation, and expose no
webhook URL, body, signature, header, or secret. Task detail shows bounded TaskItems and
ResultRecords; Job detail can navigate to its linked Task. Paged lists expose explicit Previous/Next
controls backed by stable keyset cursors, while selecting the navigation tab again returns to the
first page.
Enter a configured API principal token in the password field. The token exists only in page memory
and is cleared from the input immediately; reloading or closing the page requires entering it again.

Viewer/auditor tokens can inspect queues. Operator/executor/admin tokens may request cancellation of
pending/running Automation Jobs through an explicit two-step Job-detail control. Pending work stops
immediately; running cancellation is cooperative between items, so an in-flight operation may finish
and completed work is not rolled back. Operator/executor/admin tokens may also record the same
restricted decisions already supported by the API: conflict Skip/Rename, a persisted metadata
candidate rank, or a persisted classification choice rank. The UI cannot Overwrite, edit paths or
IDs, resume/retry/cancel a Task, or execute organization. The Jobs view can queue only `scan` or
`preview` after a separate review step, with an optional 1–10000 item limit; these jobs are visibly
marked DRY_RUN and contain no execute authority. Decisions never resume work
automatically. The standard-library server has no TLS or production identity provider; keep it on
trusted loopback or place it behind a correctly configured HTTPS reverse proxy.

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

Runtime database backup uses SQLite's online backup API, validates the snapshot, and atomically
publishes a new non-existing local file. It never overwrites. Verification opens the candidate
read-only and checks SQLite integrity plus the supported MediaFlow schema marker.

Restore is deliberately non-overwriting. Stop every MediaFlow process, verify the backup, manually
preserve/move the existing runtime database and any `-wal`, `-shm`, or `-journal` sidecars, then run
the explicitly confirmed restore command. The configured `persistence.databasePath` and all sidecars
must be absent. MediaFlow never moves, replaces, or deletes the old database for you.

On POSIX systems, runtime commands hold a shared advisory lease derived from `databasePath`; restore
must acquire the exclusive form before it validates or stages data. A running cooperating MediaFlow
CLI/API/Worker/Scheduler therefore makes restore fail immediately. The empty owner-only `.mediaflow.lock`
file is intentionally retained, contains no identifiers, and must not be deleted while processes may
run. This does not detect unrelated programs or MediaFlow code that bypasses the production CLI.

Before installing a new MediaFlow artifact, run `upgrade check` against the configured runtime
database and a fresh explicit backup. The read-only report checks Python support, application/schema
versions, backup integrity, schema agreement, and a 24-hour freshness limit. Override that bounded
operational limit explicitly when required:

```bash
mediaflow upgrade check \
  --backup /safe/backups/mediaflow.sqlite3 \
  --max-backup-age-hours 48
```

Preflight does not migrate, stop services, restore, replace, or prove live Storage connectivity.

Before allowing a newer artifact to open production Runtime state, rehearse its real forward migration
against a disposable copy:

```bash
mediaflow upgrade rehearse --backup /safe/backups/mediaflow.sqlite3
```

The command verifies and copies the backup, opens only the private copy through the production
migration repository, validates the current Schema and representative record counts, then removes the
copy and its sidecars. Runtime and backup are never migrated or replaced.

## Release validation

GitHub Actions runs the offline suite and quality checks on Python 3.11, 3.12, and 3.13, then builds
and installs the wheel into a fresh isolated environment. Run the same artifact smoke test locally:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-release.XXXXXX)
python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

The workflow has read-only repository permission and does not use production secrets or live media
services. See [docs/release.md](docs/release.md) for the complete explicit release checklist. No
artifact is automatically published or deployed.

Credential check prints only principal ID, roles, environment-variable name, enabled state, and
SET/UNSET. For rotation, temporarily configure old and new principals with different IDs and
`tokenEnv` names, restart, migrate clients, then remove the old principal and restart again.

Non-loopback HTTP is rejected by default. A bind intended for a trusted HTTPS reverse proxy needs
explicit `--allow-insecure-remote-http`; this acknowledgement does not add encryption. Prefer
loopback binding and TLS termination at a trusted proxy.

## Persistent runtime state

Production scan/preview/organize use the configured SQLite database:

```json
"persistence": {"databasePath": ".mediaflow/mediaflow.sqlite3"}
```

It stores FileIndex state, tasks, task items, normalized results, and active source locks. Config
validation does not create the database. Resume/retry creates a separately auditable task; real
mutation requires both original execute authorization and a fresh `--execute`. Existing JSONL
operation history remains compatible.

## Current milestone

The authenticated operator console now includes a read-only **System** tab. It is backed by a
precomputed `GET /api/v1/system/status` snapshot and shows bounded Storage/library/policy wiring plus
runtime compatibility. Root paths, display paths, scan-rule values, naming templates,
classification paths, endpoints, environment-variable names, arbitrary adapter options, and secrets
are intentionally excluded. Reselect **System** or use its explicit refresh button to reload the
same startup snapshot; changing JSON still requires validation and an API restart.

The core pipeline, persistent recovery/conflict decisions, attachments, read-only API queries,
persistent scan/preview jobs, Cron schedules, and signed Webhook notifications are complete.
One-time protected remote execute is available only behind its disabled-by-default feature gate.
Configuration-driven API principals, least-privilege roles, and redacted audit are complete.
The operational Dashboard and explicit metadata-review resolution are available without a Web UI.
Database-managed users/login, automatic secret rotation, scheduled execute, and extended Web UI
remain planned;
unattended scheduled real organization is not supported.

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
