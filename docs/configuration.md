# Strategy recognition configuration

The same JSON document is now the Phase 13 runtime configuration. It includes `storages`,
`resourceLibraries`, `mediaLibraries`, policy catalogs, metadata settings, and `historyPath`.
Local, OpenList, SMB, AWS S3, Cloudflare R2, and generic S3-compatible Storage definitions are
constructed by the runtime loader.
Passwords, tokens, and access keys remain environment-owned and never appear in strategy JSON.

```json
{
  "storages": [
    {"id": "source", "type": "local", "rootPath": "/media/incoming"},
    {"id": "target", "type": "local", "rootPath": "/media/organized"}
  ],
  "resourceLibraries": [
    {"id": "source-media", "storageId": "source", "storagePath": "",
     "displayRootPath": "/media/incoming"}
  ],
  "mediaLibraries": [
    {"id": "movies", "storageId": "target", "rootPath": "Movies"}
  ],
  "historyPath": ".mediaflow/history.jsonl"
}
```

Runtime configuration requires all six strategy catalogs: `recognitionRules`,
`recognitionTypePolicies`, `metadataPolicies`, `namingPolicies`, `classificationPolicies`, and
`organizePolicies`. Nothing is filled from a Python A/B/C default in production mode. The
development/smoke constructors remain test fixtures only. `config/strategy.example.json` is the
single canonical A/B/C runtime example.

Validate the entire reference graph without scanning, provider access, or Storage mutation:

```bash
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
mediaflow config validate
```

Configuration-driven discovery uses `ResourceLibrary.storagePath` as the path inside its Storage;
`displayRootPath` is only the optional local/display binding used by positional-path commands.
Legacy ResourceLibrary `rootPath` remains accepted as an alias:

```json
{"id":"movies","storageId":"source","storagePath":"Media/电影",
 "displayRootPath":"/mnt/HDD_2/Media/电影","enabled":true}
```

MediaLibrary roots are always Storage-relative:

```json
{"id":"Media","storageId":"target","rootPath":"Downloads"}
```

The standard no-path commands are:

```bash
mediaflow scan --limit 20
mediaflow preview --limit 20
mediaflow organize --limit 20
mediaflow organize --execute --limit 20
```

Only the last command authorizes mutation.

### Notification Webhooks

Notifications are opt-in and asynchronous. Configuration validation checks structure without
reading a secret or making a network request:

```json
{"notifications":{"pollSeconds":5,"deliveryLeaseSeconds":300,"webhooks":[{
  "id":"ops","url":"https://hooks.example.com/mediaflow",
  "secretEnv":"MEDIAFLOW_WEBHOOK_SECRET",
  "events":["job.completed","job.failed","job.cancelled","schedule.emitted"],
  "timeoutSeconds":10,"maxAttempts":5,"baseRetrySeconds":5,
  "maxRetrySeconds":300,"enabled":true
}]}}
```

Only HTTPS URLs without embedded credentials or fragments are accepted. Literal secrets are
rejected. Set the named environment variable only in the notification worker environment. Use
`mediaflow notifications list`, `mediaflow notifications requeue DELIVERY_ID`, and
`mediaflow notification-worker run`. A dead-letter delivery is never reactivated automatically.
An interrupted delivery becomes reclaimable only after `deliveryLeaseSeconds`. Because a receiver
may have accepted the prior attempt before the local process stopped, consumers must deduplicate
using the stable `X-MediaFlow-Delivery` header. Inspect expired leases without changing state with
`mediaflow notifications stale --age-seconds 300`.

### One-time remote execute authorization

Remote real execution is disabled unless explicitly enabled under `api.remoteExecution`:

```json
{"api":{"principals":[{
  "id":"automation-executor","tokenEnv":"MEDIAFLOW_API_TOKEN",
  "roles":["executor"],"enabled":true
}],"remoteExecution":{"enabled":true,"maximumTtlSeconds":900}}}
```

The local `execution-authorizations issue` command accepts a TTL no greater than the configured
maximum and a positive maximum item count. It prints a cryptographically random token once; SQLite
stores only its SHA-256 digest. A remote organize request must present both the normal API Bearer
and the separate token in `X-MediaFlow-Execution-Token`, specify `execute:true`, and give a positive
`limit` within the ticket bound. Token consumption and authorized Job creation are one transaction.
Tokens cannot be issued, listed, renewed, or revoked through the API. They cannot authorize
overwrite/delete by themselves and cannot be placed in schedules.
Treat the one-time raw token as a secret: avoid shared terminal capture and shell-history expansion,
submit it promptly, and revoke the authorization locally if it will not be used.

### Path model

The path fields have separate meanings:

- `Storage.rootPath`: adapter-owned root. Local roots may be absolute; OpenList roots are absolute
  OpenList API paths such as `/115网盘`.
- `ResourceLibrary.storagePath`: scan root relative to its Storage root, such as `Test_Source`.
- `ResourceLibrary.displayRootPath`: optional host-visible binding for positional-path commands.
  It does not affect no-path scanning. Legacy `rootPath` is read only as a compatibility alias.
- `MediaLibrary.rootPath`: destination root relative to its Storage root, such as `Test_Target`.

Do not repeat the Storage root inside `storagePath` or a MediaLibrary root. A cross-storage example:

```json
{
  "storages": [
    {"id":"openlist-a","type":"openlist","baseUrl":"https://a.example",
     "tokenEnv":"OPENLIST_A_TOKEN","rootPath":"/b"},
    {"id":"openlist-c","type":"openlist","baseUrl":"https://c.example",
     "tokenEnv":"OPENLIST_C_TOKEN","rootPath":"/分类"}
  ],
  "resourceLibraries": [
    {"id":"source","storageId":"openlist-a","storagePath":"",
     "displayRootPath":"/mnt/openlist-a/b"}
  ],
  "mediaLibraries": [
    {"id":"Media","storageId":"openlist-c","rootPath":"Movies"}
  ]
}
```

The plan retains `openlist-a:path` and `openlist-c:path`; a local mount path is never embedded in a
Storage-relative destination.

OpenList can be constructed by the runtime loader with non-secret settings in JSON and a token in
an environment variable:

```json
{"id":"openlist","name":"OpenList","type":"openlist",
 "baseUrl":"https://openlist.example.com","tokenEnv":"OPENLIST_TOKEN",
 "rootPath":"/Media","readOnly":false,"maxConcurrency":4,"maxRetries":2}
```

```bash
export OPENLIST_TOKEN="<token>"
```

ResourceLibrary and MediaLibrary paths referencing this Storage remain relative to `/Media`.
OpenList supports Move/Copy/Delete but not hard or symbolic links. Within one OpenList Storage, a
MOVE changing both parent and filename uses native server-side Move followed by Rename. Rename
failure triggers a best-effort Move back to the source. Cross-storage MOVE streams Copy, verifies
the destination size, and deletes the source only afterward.

SMB runtime example:

```json
{"id":"nas","type":"smb","host":"nas.example.com","share":"Media",
 "rootPath":"Incoming","usernameEnv":"SMB_USERNAME","passwordEnv":"SMB_PASSWORD",
 "domain":"WORKGROUP","port":445,"readOnly":true}
```

AWS S3, Cloudflare R2, and generic S3-compatible examples:

```json
{"id":"aws","type":"s3","bucket":"media","rootPath":"incoming",
 "accessKeyEnv":"S3_ACCESS_KEY","secretKeyEnv":"S3_SECRET_KEY","region":"ap-east-1"}
{"id":"r2","type":"r2","bucket":"media","rootPath":"incoming",
 "endpoint":"https://ACCOUNT_ID.r2.cloudflarestorage.com",
 "accessKeyEnv":"R2_ACCESS_KEY","secretKeyEnv":"R2_SECRET_KEY"}
{"id":"minio","type":"s3-compatible","bucket":"media","rootPath":"incoming",
 "endpoint":"https://minio.example.com","forcePathStyle":true,
 "accessKeyEnv":"MINIO_ACCESS_KEY","secretKeyEnv":"MINIO_SECRET_KEY"}
```

Optional temporary credentials use `sessionTokenEnv`. Literal `token`, `password`, `accessKey`,
`secretKey`, and `sessionToken` fields are rejected. Configuration validation checks these shapes
without requiring environment values or contacting a service.

```bash
mediaflow storage list
mediaflow storage check
mediaflow storage check nas
```

The list command constructs nothing. Check isolates failures and calls only existing health,
connect, and list operations; it never creates a write probe.

The loader rejects malformed JSON models, duplicate IDs, missing references, unsafe/unknown naming
templates, unsupported classification conditions, unsafe classification paths, unknown
MediaLibrary references, and unsupported organize operations before a batch starts.

`strategy-test` accepts a user JSON file through either:

```bash
strategy-test --config /path/to/strategy.json ...
```

or:

```bash
export MEDIAFLOW_STRATEGY_CONFIG=/path/to/strategy.json
```

Start from [the repository example](../config/strategy.example.json). The configuration has four
required arrays:

- `resourceLibraries`: maps a real scan root to a stable ResourceLibrary ID.
- `recognitionTypes`: configured A/B/C (or other) identities.
- `recognitionRules`: ordered rules evaluated by the production RecognitionRuleEngine.
- `recognitionTypePolicies`: independent metadata/naming/classification/organize policy references.

Metadata policies fully describe their provider, query type/MediaType, locale, thresholds, and
bounded enrichment. Locale belongs here, not in TMDBProvider:

```json
"metadataPolicies": [
  {
    "id": "A",
    "providerId": "tmdb",
    "mediaType": "movie",
    "language": "zh-CN",
    "region": "CN",
    "maxCandidateEnrichments": 2,
    "maxProviderRequests": 6
  }
]
```

Supported keys include `providerId`, `mediaType`, `mediaQueryType`, `language`, `region`,
`automaticThreshold`, `confirmationThreshold`, `minimumScoreGap`, `maxProviderRequests`, and
`maxCandidateEnrichments`. The repository example explicitly configures A/B/C as `zh-CN` and `CN`.

Naming is entirely template-driven; provider display text such as `tmdbid-` belongs in the JSON:

```json
{"id":"A","directoryTemplate":"{title} ({year}) [tmdbid-{provider_id}]",
 "filenameTemplate":"{title} ({year}).{ext}","missingVariableStrategy":"omit_token"}
```

TV policies additionally accept `seriesDirectoryTemplate`, `seasonDirectoryTemplate`,
`episodeFilenameTemplate`, and `multiEpisodeFileTemplate`. Templates use only the safe variables
and numeric formatting supported by NamingEngine; they are not an expression language.

Classification rules use normalized `conditions` and `result` objects. Supported conditions are
`mediaType`, `genres`, `countries`, `languages`, `canonicalYear`/`yearMin`/`yearMax`, and
`keywords`. The result references a configured MediaLibrary and a safe relative path:

```json
{"id":"japanese-animation","priority":200,
 "conditions":{"mediaType":["movie"],"genres":["Animation"],"countries":["JP"]},
 "result":{"mediaLibraryId":"movies","library":"Movies","path":["Anime"]}}
```

Organize policies are independent catalog entries. Valid operations are `MOVE`, `COPY`,
`HARDLINK`, and `SYMLINK`; a missing policy never falls back to MOVE:

```json
{"id":"A","operation":"COPY","overwrite":false}
```

The example mapping is:

```text
/mnt/HDD_2/Media/电影   -> resourceLibraryId movies  -> RecognitionType A
/mnt/HDD_2/Media/电视剧 -> resourceLibraryId tv      -> RecognitionType B
/mnt/HDD_2/Media/C      -> resourceLibraryId special -> RecognitionType C
```

Rules match the stable ID rather than `/mnt/HDD_2`:

```json
{
  "id": "movie-library",
  "name": "Movie resource library",
  "priority": 100,
  "score": 100,
  "stopOnMatch": true,
  "condition": {
    "field": "resource_library_id",
    "operator": "equals",
    "value": "movies"
  },
  "outputRecognitionType": "A"
}
```

Atomic `field` and `operator` strings use the values defined by `ConditionField` and
`ConditionOperator`. Logical conditions use `operator` equal to `and`, `or`, `not`, or `always`
and a `children` array. An explicit low-priority catch-all, if wanted, is represented as:

```json
{
  "id": "explicit-default-movie",
  "name": "Explicit default movie",
  "priority": -100,
  "condition": {"operator": "always", "children": []},
  "outputRecognitionType": "A"
}
```

There is no implicit default. Without a matching enabled rule, the result is `Unrecognized`.

The C policy remains independent:

```json
{
  "id": "type-C",
  "recognitionType": "C",
  "metadataPolicy": "C",
  "namingPolicy": "A",
  "classificationPolicy": "A",
  "organizePolicy": "A"
}
```

This reuses downstream policy A without rewriting RecognitionType C.

For the real movie directory:

```bash
cp config/strategy.example.json config/strategy.json
# Edit resourceLibraries roots and rules in config/strategy.json.

export MEDIAFLOW_STRATEGY_CONFIG="$PWD/config/strategy.json"
export TMDB_ACCESS_TOKEN="<your-token>"

strategy-test --directory "/mnt/HDD_2/Media/电影" \
  --live-metadata \
  --show-naming \
  --limit 20
```

For a one-off override without a root binding, the development rules also permit:

```bash
strategy-test --directory "/mnt/HDD_2/Media/电影" \
  --resource-library movies \
  --live-metadata \
  --show-naming \
  --limit 20
```

Single-file mode uses the same configured root bindings. With
`MEDIAFLOW_STRATEGY_CONFIG` exported, this automatically resolves the file to `movies`:

```bash
strategy-test --live-metadata --show-naming \
  "/mnt/HDD_2/Media/电影/千与千寻 (2001)/千与千寻 (2001).mkv"
```

An explicit single-file override is also available (`--resource-library-id` is an equivalent
backward-compatible spelling):

```bash
strategy-test --resource-library movies --live-metadata --show-naming \
  "/mnt/HDD_2/Media/电影/千与千寻 (2001)/千与千寻 (2001).mkv"
```

Root matching chooses the most specific configured containing root. If neither a binding nor an
explicit ID is available, FileContext keeps an unmatched strategy context and normal rule
evaluation may return `Unrecognized`; it never defaults to A.

Smoke case files use a separate `/A/`, `/B/`, `/C/` fixture configuration. Those path rules are
not loaded by the normal directory CLI bootstrap.

## Developer strategy-test execution

`strategy-test` remains dry-run by default. `--execution-root` may be supplied with `--show-plan`
to display the fully resolved destination without mutation. A real single-file operation requires both
`--show-plan` and `--execute`, plus an existing local destination Storage root supplied by
`--execution-root` or `MEDIAFLOW_EXECUTION_ROOT`:

```bash
strategy-test --config config/strategy.json \
  --resource-library movies \
  --live-metadata --show-plan \
  "/path/to/source/Movie.2024.mkv"

strategy-test --config config/strategy.json \
  --resource-library movies \
  --live-metadata --show-plan --execute \
  --execution-root "/path/to/destination-storage" \
  "/path/to/source/Movie.2024.mkv"
```

The first command produces `ExecutionStatus.DRY_RUN` and never accesses a mutable Storage. The
second constructs LocalStorage adapters at the selected source ResourceLibrary root and explicit
destination root. This single-local-file restriction applies only to the developer inspector.

## Production workflow

```bash
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
mediaflow config validate       # configuration only; no Storage/provider access
mediaflow scan --limit 20       # read-only discovery
mediaflow preview --limit 20    # complete pipeline, DryRun
mediaflow organize --limit 20   # complete pipeline, still DryRun
mediaflow organize --execute --limit 20
```

Without a positional path, every enabled ResourceLibrary is scanned. Production execution resolves
source and destination Storage IDs from configuration and supports configured batches. Only
`organize --execute` grants mutation authority; overwrite, implicit operation fallback, and silent
delete remain prohibited.

## Persistence and recovery

```json
"persistence": {
  "databasePath": ".mediaflow/mediaflow.sqlite3"
}
```

Relative paths use the process working directory. Runtime processing creates the database parent;
`mediaflow config validate` validates the value without creating a file or directory.

The versioned SQLite database contains persistent FileIndex, Task, TaskItem, ResultRecord, and
`StorageID + normalized source path` locks. JSONL `historyPath` remains separate and compatible.

```bash
mediaflow tasks list
mediaflow confirmations list
mediaflow confirmations show CONFIRMATION_ID
mediaflow confirmations resolve CONFIRMATION_ID --strategy rename --actor operator
mediaflow confirmations resolve CONFIRMATION_ID --strategy overwrite --confirm-overwrite
mediaflow tasks show TASK_ID
mediaflow tasks resume TASK_ID
mediaflow tasks retry-failed TASK_ID
```

Resume considers interrupted/pending/failed/partial items; retry-failed selects failed/partial
items. Successful, skipped, and DryRun results are excluded. Retry without `--execute` creates a new
DryRun task. Execute is accepted only if the original task was execute-authorized and the retry
command supplies a fresh `--execute` flag.

## Development API and background DryRun jobs

```json
"api": {
  "principals": [
    {"id": "read-only", "tokenEnv": "MEDIAFLOW_VIEWER_TOKEN",
     "roles": ["viewer"], "enabled": true},
    {"id": "automation", "tokenEnv": "MEDIAFLOW_OPERATOR_TOKEN",
     "roles": ["operator"], "enabled": true},
    {"id": "audit", "tokenEnv": "MEDIAFLOW_AUDITOR_TOKEN",
     "roles": ["auditor"], "enabled": true}
  ]
}
```

Each principal has a unique ID, unique `tokenEnv`, one or more roles, and an optional `enabled`
flag. `tokenEnv` names an environment variable and never contains the token. `config validate`
checks names and references without requiring secret values; API startup requires every enabled
principal's environment value. Literal secrets, duplicate IDs/environment names, unknown/empty
roles, and mixing `principals` with legacy `api.tokenEnv` are rejected. Legacy `tokenEnv` alone is
still interpreted as one admin principal for backward compatibility.

Generate and inspect credentials without connecting to Storage or opening SQLite:

```bash
mediaflow api token generate                 # 32 random bytes by default
mediaflow api token generate --bytes 64      # supported range: 32..128
export MEDIAFLOW_VIEWER_TOKEN='<generated value>'
mediaflow --config config/strategy.json api credentials check
```

`credentials check` never displays values, lengths, or hashes. An enabled UNSET credential makes
the command fail; disabled credentials are informational. For manual zero-downtime rotation,
temporarily configure two principals with distinct IDs and environment names, restart, migrate
clients, then disable/remove the old principal and restart. Never put either value in JSON.

Role permissions are fixed and additive:

| Role | Read | Submit DryRun | Cancel Job | Resolve conflict | Resolve metadata | Resolve classification | Remote execute | Security audit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `viewer` | yes | no | no | no | no | no | no | no |
| `operator` | yes | yes | yes | yes | yes | yes | no | no |
| `executor` | yes | yes | yes | yes | yes | yes | yes | no |
| `auditor` | yes | no | no | no | no | no | no | yes |
| `admin` | yes | yes | yes | yes | yes | yes | yes | yes |

Remote execute also requires the Phase 18.5 feature flag and a separate valid one-time execution
token. An executor role never bypasses that second gate or conflict/overwrite protections.

Operator, executor, and admin roles additionally have `resolve_confirmation` and
`resolve_metadata_review` and `resolve_classification_review`. Viewer and auditor remain read-only. Remote overwrite is forbidden for
every role and remains available only through the explicit local CLI confirmation flow.

```bash
export MEDIAFLOW_VIEWER_TOKEN='<long-random-viewer-token>'
export MEDIAFLOW_OPERATOR_TOKEN='<independent-random-operator-token>'
export MEDIAFLOW_AUDITOR_TOKEN='<independent-random-auditor-token>'
mediaflow jobs submit scan --limit 20
mediaflow jobs submit preview --limit 20
mediaflow jobs list
mediaflow jobs show JOB_ID
mediaflow jobs cancel JOB_ID
mediaflow worker run-next
mediaflow dashboard --recent-limit 10
mediaflow api serve --host 127.0.0.1 --port 8787
mediaflow security-audit list --limit 100
```

The same process serves the minimal operator UI at `http://127.0.0.1:8787/ui/`. It adds no JSON
configuration. Its API token is entered after page load and retained only in JavaScript memory—no
cookie or browser storage is used. Use a `viewer` principal for read-only visibility or an
`operator` principal for the existing safe review decisions. The UI deliberately excludes remote
Overwrite, execution authorization, Job/Task controls, policy editing, and Storage configuration.
Serve on loopback by default; this development WSGI server does not terminate TLS.

Task and Job visibility uses bounded authenticated reads:

```text
GET /api/v1/tasks?limit=100
GET /api/v1/tasks?limit=100&cursor=OPAQUE_CURSOR
GET /api/v1/tasks/{id}?itemLimit=100&resultLimit=100&itemCursor=...&resultCursor=...
GET /api/v1/jobs?limit=100
GET /api/v1/jobs?limit=100&cursor=OPAQUE_CURSOR
GET /api/v1/jobs/{id}
GET /api/v1/schedules
GET /api/v1/schedules/{id}/audit?limit=100
GET /api/v1/schedules/{id}/audit?limit=100&cursor=OPAQUE_CURSOR
GET /api/v1/notifications?limit=100&status=all
GET /api/v1/notifications?limit=100&status=dead-letter&cursor=OPAQUE_CURSOR
```

Collection and detail limits are 1–100. Responses include truncation metadata. These UI views never
submit, cancel, resume, retry, authorize, or execute work.

Use returned `previous_cursor`/`next_cursor`, `previous_item_cursor`/`next_item_cursor`, or
`previous_result_cursor`/`next_result_cursor` unchanged in the matching endpoint. Emitted v2 cursors
carry a strict direction; valid Phase 19.4 v1 cursors remain accepted as forward cursors. Cursors are
URL-safe and resource-specific. They contain only a UTC ordering timestamp and stable record ID—never
media paths, titles, errors, provider data, or secrets. Do not reuse a cursor across resources.
Task/Job pages remain newest-first; TaskItem/Result pages remain oldest-first. Pagination uses
keyset boundaries, not page numbers, total scans, or OFFSET, so arbitrary jumps are intentionally absent.

The Schedules UI combines safe configuration fields with persisted next-run/last-job state. Its
occurrence audit is newest-first and paged in bounded 1–100-row reads. Notifications accept `all`, `pending`,
`delivering`, `retry`, `delivered`, or `dead-letter`; the UI provides an explicit status selector and
refresh and scoped Previous/Next controls but never polls automatically. Notification cursors bind
the selected status; schedule-audit cursors bind the schedule ID, so cross-filter or cross-schedule
reuse fails. Delivery output excludes webhook URLs, payload bodies,
signatures, headers, response bodies, and secrets. Neither view exposes schedule ticking/editing or
notification delivery/requeue controls.

Wildcard, LAN, and public binds require `--allow-insecure-remote-http`. The flag only acknowledges
unencrypted transport; it does not enable TLS. Prefer loopback behind a trusted HTTPS reverse proxy,
restrict network access, and never treat forwarded headers as authenticated identity.

The Worker claims one oldest pending job atomically and delegates it to the existing production
workflow. Preview is always DryRun. `/api/v1` requires the bearer token and supports read-only
Task/Job/Confirmation queries plus scan/preview submission and pending cancellation. Remote
organize is rejected unless the separately documented one-time execution feature is enabled and a
valid ticket is atomically consumed. The server is a loopback development adapter, not a hardened
Internet-facing deployment.

`dashboard` needs no additional configuration. It counts enabled libraries from this runtime
document and persisted state from `persistence.databasePath`; it does not resolve Storage/provider
secrets or test connections. The API equivalent is `GET /api/v1/dashboard?recentLimit=10` and uses
the ordinary read permission. `recentLimit` must be between 1 and 50.

Confirmation reads use the same read permission:

```text
GET /api/v1/confirmations?status=pending&limit=100
GET /api/v1/confirmations/{id}
GET /api/v1/confirmations/{id}/audit
```

The bounded list accepts `pending`, `resolved`, or `all`. Principals with
`resolve_confirmation` may submit `POST /api/v1/confirmations/{id}/resolve` with exactly one JSON
field, `strategy`, whose value is `skip` or `rename`. The authenticated principal ID is the audit
actor; client actor/note/path/overwrite/execute/token fields are rejected.

`GET /api/v1/security-audit` is restricted to auditor/admin. SQLite audit rows record timestamp,
principal ID when known, method, normalized route, action/outcome/status, request ID, and a bounded
source address. They deliberately omit query strings, headers, bodies, cookies, credentials,
media values, and error text. Local audit listing constructs no Storage adapter.

Metadata-review visibility needs no additional configuration. NeedConfirm/Ambiguous results are
persisted in `persistence.databasePath` and can be inspected with:

```bash
mediaflow metadata-reviews list --limit 100
mediaflow metadata-reviews show REVIEW_ID
```

The API equivalents are `GET /api/v1/metadata-reviews?limit=N` and
`GET /api/v1/metadata-reviews/{id}`; `N` must be between 1 and 100. These reads use ordinary read
permission and never construct Storage or MetadataProvider adapters. They expose bounded scoring
evidence only, not credentials, provider payloads, overview/images, headers, or raw errors.

An operator/executor/admin may resolve exactly one persisted candidate rank with
`POST /api/v1/metadata-reviews/{id}/resolve` and body `{"candidateRank":1}`. Provider IDs, actor,
paths, policies, and execute fields cannot be supplied. Resolution only records the decision and
makes the original item pending; `mediaflow tasks resume TASK_ID` is a separate explicit action and
requires `TMDB_ACCESS_TOKEN` for canonical provider details.

Classification review uses the same persistence database and no additional configuration:

```text
GET  /api/v1/classification-reviews?limit=100
GET  /api/v1/classification-reviews/{id}
POST /api/v1/classification-reviews/{id}/resolve
     {"choiceRank":1}
```

Only rules already configured and enabled in the resolved ClassificationPolicy appear as choices.
The POST body cannot contain a path, MediaLibrary ID, rule ID, actor, or execute field. Resolution
is persistence-only; a separate local `mediaflow tasks resume TASK_ID` revalidates the configured
rule before continuing.

### Resident Worker, interval schedules, and Cron

```json
"automation": {
  "workerPollSeconds": 2,
  "schedulerPollSeconds": 5,
  "schedules": [
    {"id": "hourly-scan", "command": "scan", "intervalSeconds": 3600,
     "limit": 20, "enabled": false},
    {"id": "cn-morning-preview", "command": "preview", "cron": "0 8 * * *",
     "timezone": "Asia/Shanghai", "limit": 20, "enabled": false}
  ]
}
```

IDs are unique; command is only `scan` or `preview`; intervals and limits are positive. The first
enabled tick emits one job and persists its next-run time. Missed periods do not create a backlog.

```bash
mediaflow scheduler list
mediaflow scheduler tick
mediaflow scheduler run
mediaflow scheduler audit
mediaflow scheduler audit cn-morning-preview --limit 100
mediaflow worker run
mediaflow jobs cancel JOB_ID
mediaflow jobs stale --age-seconds 3600
mediaflow jobs requeue JOB_ID --age-seconds 3600
```

Worker/Scheduler stop gracefully on SIGINT/SIGTERM. Running cancellation is cooperative between
items. Stale jobs require an explicit age-guarded requeue because prior external work is uncertain.

A schedule configures exactly one of `intervalSeconds` or `cron`. Cron has five numeric fields:
minute, hour, day-of-month, month, and day-of-week (Sunday is 0). It supports `*`, comma lists,
inclusive ranges, and positive steps on `*` or a range. Restricted day-of-month/day-of-week use OR
semantics. Names, macros, seconds, reversed ranges, and shell content are rejected. IANA `timezone`
is mandatory. UTC instants are persisted and CLI displays UTC/local values. Nonexistent DST wall
times are skipped; ambiguous times use fold 0 and emit once. Each emission creates immutable audit.
An organize policy also controls conflict behavior:

```json
{
  "id": "A",
  "operation": "MOVE",
  "conflictStrategy": "manual",
  "overwrite": false
}
```

`conflictStrategy` is one of `skip`, `rename`, `manual`, or `overwrite`. The default is `manual`.
Legacy `overwrite: true` maps to `overwrite`, but contradictory values fail validation. Overwrite
still requires a persistent explicit decision made with `--confirm-overwrite`; configuration alone
never authorizes mutation. `mediaflow config validate` only validates and never accesses Storage.

Attachment discovery is separately opt-in on each OrganizePolicy:

```json
"attachments": {
  "enabled": true,
  "subtitles": true,
  "nfo": true,
  "artwork": true,
  "trailers": true,
  "otherSameStem": false
}
```

The omitted/default policy is disabled. Discovery performs one read-only `Storage.list` on the
primary media directory. Supported subtitles are `srt`, `ass`, `ssa`, `vtt`, `sub`, and `sup`;
language plus `forced`, `sdh`, and `hi` suffixes are preserved. Same-stem NFO, conventional
poster/fanart, related images, and same-stem `-trailer`/`.trailer` videos are supported. Enabling
`otherSameStem` deliberately broadens matching but still requires a safe same-stem boundary.
Unknown and disabled files are never deleted.

The canonical safe starter is [`config/strategy.example.json`](../config/strategy.example.json),
where attachment processing is explicitly disabled. The exhaustive field and operation catalog is
[`config/mediaflow.phase13.2.example.json`](../config/mediaflow.phase13.2.example.json); its main
MOVE policy demonstrates enabled attachment handling, while the embedded catalog shows attachment
settings for MOVE, COPY, HARDLINK, and SYMLINK.
