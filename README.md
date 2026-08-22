# MediaFlow

MediaFlow is a safety-first media organizer with Storage adapters for Local, SMB, OpenList, and
S3/R2. Its production pipeline scans media, parses filenames, recognizes a configured type,
identifies metadata, calculates names and classification, plans an operation, and optionally
executes it. Dry-run is always the default.

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
```

## CLI

```bash
mediaflow analyze "/path/to/movie.mkv"
mediaflow analyze --offline "/path/to/movie.mkv"
mediaflow config validate
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
mediaflow api serve --host 127.0.0.1 --port 8787
```

`preview` and `organize` without `--execute` produce DryRun results. Only `organize --execute`
permits Storage mutations. Existing destinations enter the configured Skip/Rename/Manual/Overwrite
decision flow. Overwrite is rejected unless the OrganizePolicy enables it and the user records a
fresh `--confirm-overwrite` decision; unresolved conflicts remain non-mutating.
Silent deletion is not enabled.

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

Phase 18.1 adds a local development WSGI API and a persistent background queue. Configure only the
environment-variable name in JSON:

```json
"api": {"tokenEnv": "MEDIAFLOW_API_TOKEN"}
```

`GET /health` is public. Every `/api/v1` request requires
`Authorization: Bearer $MEDIAFLOW_API_TOKEN`. The API can query tasks, jobs, and pending
confirmations, and it can queue only `scan` or `preview`. Run one queued item with
`mediaflow worker run-next`; preview is always DryRun. Remote organize/execute, overwrite, delete,
and conflict resolution are rejected. This standard-library server is for trusted loopback
development use, not direct Internet exposure.

Phase 18.2 adds a resident Worker and opt-in interval schedules. Example schedules are disabled by
default. Run Scheduler and Worker separately. `jobs cancel JOB_ID` cancels pending work immediately
or requests cooperative cancellation of running work before another media item starts; an in-flight
read may finish. Stale crash leftovers are never retried automatically: inspect with
`jobs stale --age-seconds N` and explicitly use `jobs requeue JOB_ID --age-seconds N`.

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

The core pipeline, persistent recovery/conflict decisions, attachments, read-only API queries, and
persistent scan/preview jobs are complete. Scheduler/Cron, notifications, protected remote execute,
and Web UI remain planned; unattended real organization is not supported.
