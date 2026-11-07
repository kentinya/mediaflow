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
business authority. The retained V1 `/ui` is a historical surface; V1 is unsupported on this line.
[Documentation](docs/README.md) maps document
responsibilities. [Roadmap](docs/roadmap.md) records priority/status,
[Progress](docs/progress.md) accepted closures, and [SLICE.md](SLICE.md)/[TASK.md](TASK.md) current work.
The accepted V2 baseline includes live library/Storage management, typed Rules, Files-first organizing,
a Task-owned execution queue and same-Task four-type recovery. Ordinary file progress stays on its
originating library page; Task Center handles organizing. Live Job, Pause/resume-from-pause and CLI
`tasks retry-failed` are retired. Scan/Preview/FileIndex retirement remains intact. Three shared
runtime settings live in System Settings. Five-state Task flow stays independent of file outcomes;
completion neither proves file success nor grants replay.

[Slice49](https://github.com/kentinya/mediaflow/blob/6cd881f0311c9e53bfc6b0ab754bfbe9acefbfd0/SLICE.md) is PASS / CLOSED: Automation uses confined saved sources, direct list Run once,
a shared Chinese create/edit card and optional enabled creation. The subsequent accepted UI
correction places Copy beside Edit and uses a compact enable switch saved through the form.
[Slice51](SLICE.md) is PASS / CLOSED after independent A Final Review on 2026-11-07:
TMDB Explore is the default homepage, with browse → filter/search → detail → return, truthful empty
states and independent read recovery. Dashboard Web/API/CLI, dedicated backend and consumers have
fully retired without compatibility; shared statistics and durable history remain. Original Base
`214b69b1e64b24fc22068c2e1760cd1b0c6ac787` through implementation `30c99f1bdcd9be2cb51ac82f78bc4b07eaea3113` is accepted.
[CURRENT requirements](docs/v2-requirements.md#current--v2-explore-homepage-slice51-pass--closed) define the delivered boundary.
[TASK.md](TASK.md) records no active implementation Task; selecting the next large Slice is a
separate A action. The user-authorized B planning substitutions remain disclosed in
the Contract; Task acceptance and A Final Review were independent. Development acceptance is
distinct from a release or deployment.

[Slice50](https://github.com/kentinya/mediaflow/blob/214b69b1e64b24fc22068c2e1760cd1b0c6ac787/SLICE.md) is PASS / CLOSED after independent A Final Review on 2026-11-07: readable Task
cards, Storage/library cards and menus, both page-local trees removed, nine main-page transitions,
consistent library loading and stable Automation create/edit. [CURRENT requirements](docs/v2-requirements.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)
preserve existing business/safety boundaries. [Progress](docs/progress.md) keeps original Base/Head,
closure evidence, deferrals and validation limits. This is unreleased V2 development acceptance.

The subsequent [accepted readability/navigation correction](https://github.com/kentinya/mediaflow/blob/db54158dbb5ee9df3b67c26f38999ba87ea6281a/TASK.md) presents Task details as flow status → processed range → file results. File evidence explains the
captured work identity, naming and classification before technical diagnostics. Cancellation appears
with Task actions when available. Automation has no standing header refresh button; failed reads
retain local reload actions and successful commands update the list.

The current [Task Center](docs/task-center-page-spec.md) has no shared top search. All eight views
offer only the local creation-date range and clear. Clearing restores the current view’s complete
authorized population with normal paging. Manual refresh uses Chinese busy feedback; background
polling updates quietly and normal same-query refresh preserves visible content and context.

The [Rules workspace](docs/configuration.md#native-v2-organizing-rules-management) keeps its title,
description and refresh in the content header. Overview has no inventory search; each of the seven
families keeps one local search and state filter. Settings retains configuration diagnostics/recovery.

The [Automation workspace](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
contains `任务列表 / 执行记录`; the three shared runtime settings live in System Settings.
`新建自动化任务` and a row's `编辑` open the same Chinese card for source, schedule, limit and
explicit enablement. Creation defaults disabled; choosing `启用定时计划` uses `创建并启用`.
Editing can later enable/disable through the same compact switch and Save; cancellation or success
preserves list context. The list and its create/edit backgrounds have no extra location-label row.
A row's actions are `打开 / 编辑 / 复制 / 运行一次`, subject to backend permissions. Copy stays in the
list, creates a disabled definition with a new ID and offers `编辑副本`, including when filters/paging
hide it. An unknown copy uses `核对复制结果` for that original command; it is never automatically
reposted. Concurrent changes require rereading the displayed source and its matching authority before
a new explicit click. Publishing runs no media work. Unknown creation/publication is reconciled
before further commands. A row's
`运行一次` directly submits the saved definition in place; use its `查看任务` link for progress/results.
An unknown Run once uses `查看提交结果` to reconcile the original request without resubmitting.
Execution-record rows offer only `查看详情 / 收起详情`;
details show the current Task flow result, original actual times, independent file outcomes, a concise
Chinese failure reason when the flow failed, and a short next step. Records and Task Center read the
same durable flow state, with server filters/counts/paging applied before page limits. Failed files,
unknown effects or absent Results do not relabel a completed flow as failed; file success cannot
override failed flow. Legal continuation can change current flow state without adding another run
or rewriting original times/attempts/file effects. Proven no-work and unavailable evidence stay distinct.
The local-month success rate is completed/(completed+failed) for original scheduled due and definition
Run once Tasks. Cancelled/unfinished Tasks, Files/CLI manual organizing and ordinary file operations
are excluded from both numerator and denominator. No evaluated Tasks means no percentage; cancelled
Tasks remain in records and all-ended counts. See the [current flow/rate journey](docs/product-experience.md#current--task-flow-status-and-automation-success-rate-slice48-pass--closed).
Definition management and organizing recovery use their own workspace entries.

## V2 frontend (web/)

React/TypeScript/Vite, TanStack Router/Query and a central typed API boundary render `/ui-v2/`.
Tokens stay in browser memory. Python serves built static assets; Node is build/development tooling.

```bash
npm --prefix web ci
npm --prefix web run build
mediaflow api serve --host 127.0.0.1 --port 8787
```

Open `/ui-v2/` and connect a configured API-principal token. Reload requires reconnecting.
The retained `/ui/` belongs to the unsupported historical V1 surface on this development line.
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
| Pause/resume/retry | Organizing and ordinary-file Pause/resume are retired; cancellation stops unperformed work at a safe boundary, and four-type recovery continues the same Task through analysis, summary and explicit confirmation. A continuation cannot upgrade analysis-only work or regain consumed authority. |
| Stalled Task | Inspect the Worker and Storage effects before explicit permitted recovery; staleness is no-update evidence, not proof of death or permission to replay an uncertain mutation. |
| Notifications | Signed HTTPS Webhook Outbox; bounded transport/429/5xx retry, other 4xx dead-letter, stable delivery identity for at-least-once deduplication. Recovery is delivery-scoped and never changes media results. |
| Policy options | Read-only retry is bounded/default-off and excludes mutations. Hash defaults NONE, FAST is prefix evidence, failed/unknown comparison never authorizes overwrite. Attachments and source cleanup are opt-in. Rollback compensates only verified effects of the same failed invocation, never changed targets/reappeared sources/older work. |

Full operator journeys and failure/recovery semantics are in [Product Experience](docs/product-experience.md);
policy fields and exact constraints are in [Requirements](docs/requirements.md) and the example config.

## Development API and execution authority

API requests use `Authorization: Bearer ...` with environment-owned principal references and
viewer/operator/executor/auditor/admin roles. `/health` is public. Executor permission alone is not
mutation authority. Keep local API tokens, Webhook secrets and Storage credentials independent.

### Remote API execution authorization

For explicitly enabled remote API automation, locally issue a short-lived single-use authorization:

```bash
mediaflow execution-authorizations issue --ttl-seconds 300 --max-items 20
curl -X POST http://127.0.0.1:8787/api/v1/tasks \
  -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  -H "X-MediaFlow-Execution-Token: <one-time-token>" \
  -H "Content-Type: application/json" \
  --data '{"command":"organize","execute":true,"limit":20}'
```

`api.remoteExecution.enabled` defaults false; configure the principal and TTL ceiling explicitly.
The raw value is displayed once, only its digest persists, and admission/consumption is atomic.
The response is `202` with the admitted `taskId` and its `task` read address; the submitted work is
the ordinary organizing Task shown in the Task center. Only `command:"organize"`, `execute:true`
and `limit` are accepted — the retired Job collection and its submission/cancel/requeue aliases are
not available. Use `mediaflow tasks cancel TASK_ID` (or the Task center) for cooperative cancellation.
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
Backup and same-version restore are separate maintenance operations, with non-overwrite/verified backup,
all-process stop, destination/sidecar absence and advisory-lease rules in
[offline restore](docs/release.md#offline-restore-procedure). Old-task/Job migration or takeover,
cross-version upgrade/rollback and mixed-version writers are outside current support.

## Persistent runtime state

SQLite persists managed configuration, Task/item/results, work evidence, locks, authority,
notifications and audit. A Task is the only organizing-work identity: there is no independent Job
table, Job queue or Job worker. JSONL operation history remains supported. Managed Active overrides JSON
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
| [Deployment](docs/deployment.md) | Start/health, mounts/secrets, restart, backup, same-version recovery and production artifacts |
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
