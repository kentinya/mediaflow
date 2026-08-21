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
mediaflow tasks show TASK_ID
mediaflow tasks resume TASK_ID
mediaflow tasks retry-failed TASK_ID --execute
```

`preview` and `organize` without `--execute` produce DryRun results. Only `organize --execute`
permits Storage mutations. Existing destinations and unresolved conflicts are rejected; overwrite
and silent deletion are not enabled.

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

The core CLI pipeline and Phase 14 persistence foundation are complete. Interactive conflict
handling is next; attachments, scheduling, API, and Web UI remain planned. A scheduler is not yet
implemented, so unattended execution remains outside the supported workflow.
