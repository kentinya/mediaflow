# MediaFlow

MediaFlow organizes media through configured Storage, filename/path/NFO parsing, recognition,
metadata, naming, classification and exact plans. Local, SMB, OpenList and S3-compatible Storage
(including AWS S3 and Cloudflare R2 adapters) share one pipeline. DryRun is the default;
only explicitly authorized OrganizerExecutor work mutates media. No FFmpeg/FFprobe is used.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev,tmdb]'
cp config/strategy.example.json config/mediaflow.json
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
export TMDB_ACCESS_TOKEN="<token>"
export MEDIAFLOW_API_TOKEN="<long-random-development-token>"
```

Edit Storage roots and library-relative paths before use. Credentials stay in environment variables;
JSON stores references. Optional provider extras are `openlist`, `smb`, `s3`; their credential
references are described in [Configuration](docs/configuration.md). `storage list` does not connect
adapters; `storage check` is a bounded read-only check, not mutation authority.

For production installation, use [Docker deployment](docs/deployment.md). A management-only bootstrap
can start without media mounts or business objects; Web Settings creates and activates managed
configuration. Local media access requires explicit container-visible mounts and permissions.

## V1 self-hosted release status

V1 `1.0.0` is released at `v1.0.0` on `release/v1`: one image, independent API/Worker/Scheduler/
Notification Worker services, local `/data` persistence and Waitress production serving.
[Release](docs/release.md) owns release validation and [Storage acceptance](docs/storage-acceptance.md)
the bounded real-service evidence. Samba/OpenList-Local-driver/MinIO evidence does not certify
AWS/R2, other OpenList drivers, remote atomic publication, power loss or multi-hour soak.

## V2 development status

`main` is the unreleased `2.0.0.dev0` Operator Web development trunk. Python `/api/v1/*` remains the
business authority and V1 `/ui` remains available. [Documentation](docs/README.md) maps document
responsibilities. [Roadmap](docs/roadmap.md) records priority/status,
[Progress](docs/progress.md) accepted closures, and [SLICE.md](SLICE.md)/[TASK.md](TASK.md) current work.
Slice43 is PASS / CLOSED: native Automation lifecycle, bounded Run once, read-only records/statistics
and engine settings with actual resident adoption are accepted. Slice45's Task Center and retired
Scan/Preview/FileIndex boundaries remain intact; V2 is still unreleased and V1 cutover is not selected.
Slice46 is PASS / CLOSED: readable V2 actions, Files-first admitted organizing, library-local ordinary
operation status, organizing-only eight-view/four-type Task Center and checked Enabled/real Run once
are accepted. No active implementation Task remains; A selects the next large Slice separately.

## V2 frontend (web/)

React/TypeScript/Vite, TanStack Router/Query and a central typed API boundary render `/ui-v2/`.
Tokens stay in browser memory. Python serves built static assets; Node is build/development tooling.

```bash
npm --prefix web ci
npm --prefix web run build
mediaflow api serve --host 127.0.0.1 --port 8787
```

Open `/ui-v2/` or V1 `/ui/` and connect a configured API-principal token. Reload requires reconnecting.
The development listener is trusted-loopback only; production exposure/TLS/proxy rules belong to
[Deployment](docs/deployment.md). Frontend test commands and B-owned full gates are centralized in
[Development Workflow](docs/development-workflow.md#6-test-levels); Playwright requires Chromium.

## CLI

### Current live file lists

[The accepted live-list contract](docs/file-index-retirement-spec.md) defines library-scoped Storage
lists shared by CLI, Files and MediaLibrary,
with no catalog/observation/work recording or execution authority from listing:

```bash
mediaflow files list --resource-library source --path "incoming" --limit 100
mediaflow files list --media-library media --path "Movies" --limit 100
```

Choose exactly one library, omit `--path` for its root and use the returned `--cursor` for the next
page. Global indexed filters/detail/statistics are removed. Complete FileIndex removal
and the prelaunch/no-old-migration boundary are in [the retirement design](docs/file-index-retirement-spec.md).
Task-scoped sources/results/audit remain durable. No existing data/media is automatically cleared.

Standalone Scan and scan-only/scan-and-plan modes have been removed from the current implementation;
old inputs receive ordinary not-found/argument errors. Shared internal discovery, filters, genuine
stability observations and zero-mutation planning remain. Independent Preview is also removed.

### Current organizing analysis and confirmation

[The Preview retirement contract](docs/preview-retirement-spec.md) uses the same first-deployment
absence standard as Scan: independent Preview pages/API/CLI/Jobs/schedules/dispatch/continuation,
exclusive persistence/composition and compatibility layers are removed. Old inputs use ordinary not-found or
unsupported-argument/type errors; no retirement page/410, automatic conversion or old production
migration/history/takeover framework. New manual organizing starts from ResourceLibrary Files;
Task Center owns its progress and four-type recovery under accepted Slice46.

Explicit Files organizing admits a durable task before business readiness, then keeps exact same-page
analysis/summary and separate selected execution confirmation. Automation checked Enabled supplies
future scheduled intent; Run once directly executes its saved bounded scope with current permission,
without an independent grant/pre-analysis or second initial confirmation. Four-type recovery still
requires explicit safe continuation. `mediaflow organize` without `--execute` and Rules/configuration
checks retain shared zero-media-mutation analysis. Separate analysis creates no organizing authority
or backlog; exact plans/pins/results/audit stay durable and no existing data/media is cleared.

### Baseline command reference

Use `mediaflow --help` and `mediaflow <command> --help` for the complete current argument reference.
Common current workflows:

```bash
mediaflow config validate
mediaflow config status
mediaflow storage list
mediaflow storage check
mediaflow analyze --offline "/path/to/movie.mkv"
mediaflow organize --limit 20
mediaflow organize --execute --limit 20
mediaflow worker run
mediaflow tasks list
mediaflow tasks show TASK_ID
mediaflow scheduler run
mediaflow notification-worker run
```

No-path Organize uses enabled ResourceLibraries. Organize without `--execute`
is zero-mutation. Overwrite requires enabling policy and fresh explicit consent; conflict/capability
checks remain mandatory. Link operations never silently fall back. The `strategy-test` inspector
remains available for local development diagnostics.

| Operation | Safe behavior / next action |
|---|---|
| Recognition/Metadata/Classification review | Resolve only backend-offered type/candidate/rule choices; saving never executes. Continue through the Task's same-page analysis, summary and explicit confirmation. No arbitrary target or Provider DTO injection. |
| Conflict decision | Persist an allowed decision, re-analyze and separately authorize execution. Successful/uncertain items are never replayed. Retired direct re-recognition/re-match/re-plan/review-retry surfaces stay absent. |
| Pause/resume/retry | Cooperative boundaries preserve in-flight outcomes and prior scope/pin; a continuation cannot upgrade DryRun or regain consumed authority. CLI mutation continuation needs explicit current execution authority. |
| Stale Job | Inspect Worker and Storage effects before explicit permitted recovery; stale age is no-update evidence, not proof of death or permission to replay uncertain mutation. |
| Notifications | Signed HTTPS Webhook Outbox; bounded transport/429/5xx retry, other 4xx dead-letter, stable delivery identity for at-least-once deduplication. Recovery is delivery-scoped and never changes media results. |
| Policy options | Read-only retry is bounded/default-off and excludes mutations. Hash defaults NONE, FAST is prefix evidence, failed/unknown comparison never authorizes overwrite. Attachments and source cleanup are opt-in. Rollback compensates only verified effects of the same failed invocation, never changed targets/reappeared sources/older work. |

Full operator journeys and failure/recovery semantics are in [Product Experience](docs/product-experience.md);
policy fields and exact constraints are in [Requirements](docs/requirements.md) and the example config.

## Development API and DryRun worker

API requests use `Authorization: Bearer ...` with environment-owned principal references and
viewer/operator/executor/auditor/admin roles. `/health` is public. Executor permission alone is not
mutation authority. Keep local API tokens, Webhook secrets and Storage credentials independent.

### Current V1 / API execution-authorization mechanism

For explicitly enabled remote API automation, locally issue a short-lived single-use authorization:

```bash
mediaflow execution-authorizations issue --ttl-seconds 300 --max-items 20
curl -X POST http://127.0.0.1:8787/api/v1/jobs \
  -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  -H "X-MediaFlow-Execution-Token: <one-time-token>" \
  -H "Content-Type: application/json" \
  --data '{"command":"organize","execute":true,"limit":20}'
```

`api.remoteExecution.enabled` defaults false; configure the principal and TTL ceiling explicitly.
The raw value is displayed once, only its digest persists, and admission/consumption is atomic.
The V2 Web journey instead holds exact-plan authority on the server after review and explicit
confirmation; ordinary users do not issue or transfer tokens. Both retain RBAC, pins, effect scope,
audit, fencing and OrganizerExecutor-only mutation. See [Architecture](docs/architecture.md#interactive-execution-authorization-current-v1-and-v2).

### Operator Web UI

Use Web for normal management, file work and recovery. [Configuration](docs/configuration.md)
explains managed Draft/Validated/Active lifecycle and page-local checked Save. The Task center
shows actual per-item results and legal next actions; unknown submissions are read back before
another attempt, and uncertain effects require investigation.

Operational logs and security audit are bounded/redacted; reads expose no credentials, raw request
bodies or Provider payloads. Log pruning touches neither media nor Tasks/Results/security audit.
Backup/restore/upgrade are separate maintenance operations, with non-overwrite/verified backup,
all-process stop, destination/sidecar absence and advisory-lease rules in
[offline restore](docs/release.md#offline-restore-procedure).

## Persistent runtime state

SQLite persists managed configuration, Task/Job/item/results, work evidence, locks, authority,
notifications and audit. JSONL operation history remains supported. Managed Active overrides JSON
bootstrap after activation and work pins immutable snapshots. Config validation creates no runtime
database. FileIndex is removed; live listing reads the existing managed Active and internal cursor
key without database initialization/migration. Missing initialization provides setup guidance.

**Concurrent Local directory Delete:** pause other writers before confirming deletion. Some
filesystems can reuse an inode between final metadata revalidation and deletion, making a same-name
replacement indistinguishable. If the directory changed or can be recreated concurrently, stop,
refresh and review again after writers are quiescent. No claim of atomic external-writer exclusion.

## Configuration and architecture

| Guide | Owns |
|---|---|
| [Configuration](docs/configuration.md) | Bootstrap, exact Active, library/policy forms, secret references and checked publication |
| [Product Experience](docs/product-experience.md) | Current and target journeys, visible results, failure and recovery |
| [Architecture](docs/architecture.md) | Pipeline, application authority, Storage, persistence and execution boundaries |
| [Deployment](docs/deployment.md) | Start/health, mounts/secrets, restart, backup, migration and production artifacts |
| [Requirements](docs/requirements.md) / [V2 requirements](docs/v2-requirements.md) | Stable product scope/IDs and explicit amendments |
| [Release](docs/release.md) / [Storage acceptance](docs/storage-acceptance.md) | Release gates and bounded real-service evidence |

Detailed past Task/audit/review packets live in Git; [Progress](docs/progress.md) retains accepted
Base/Head/closure facts and historical lookup pointers. `docs/history/` is immutable legacy evidence.

## Development workflow

Read [AGENTS.md](AGENTS.md), [Development Workflow](docs/development-workflow.md), committed Slice
and active Task. A owns scope/final review; Developer implements and runs new/changed/directly
affected tests; B owns Task review/full acceptance. Use [Task template](Task/TEMPLATE.md).

## Release validation

CI runs offline Python quality/tests and isolated wheel smoke checks without production secrets or
media and does not publish/deploy automatically. B's full gates, applicable packaging/real-browser/
Docker checks, and concise evidence rules live in [Development Workflow](docs/development-workflow.md#6-test-levels).
