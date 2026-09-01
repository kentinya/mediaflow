# Architecture

## Structure and dependency direction

MediaFlow uses a ports-and-adapters layout:

```text
infrastructure adapters -> domain ports <- application use cases
```

`mediaflow.domain` owns immutable models and protocols and imports no infrastructure.
`mediaflow.application` coordinates ports. `mediaflow.infrastructure` implements ports, currently
including Local, SMB, OpenList, and S3/R2 Storage adapters. Future API, database, and TMDB adapters
also stay outside the domain.

The major boundaries are Storage, ResourceLibrary, MediaLibrary, Scanner, Parser, Recognition,
RecognitionTypePolicy, Metadata, Naming, Classification, Organizer, Tasks, and Logging. Protocols
are intentionally small bootstrap contracts rather than complete implementations.

## Processing pipeline

```text
ResourceLibrary -> Scan -> Parse -> RecognitionRule -> RecognitionType
-> RecognitionTypePolicy -> Metadata -> Naming -> Classification
-> OrganizePlan -> OrganizerExecutor -> Result
```

RecognitionTypePolicy holds independent metadata, naming, classification, and organize policy
references. Type C can therefore use metadata C and naming/classification A while remaining C.

Phase 13 exposes this complete application flow through `MediaOrganizerService`:

```text
Scanner -> Parser -> Recognition -> Metadata -> MediaIdentity -> Naming -> Classification
-> OrganizePlan -> OrganizerExecutor -> ExecutionResult -> OperationHistoryRepository
```

The service is deliberately orchestration-only. Scanner owns traversal/filtering, existing engines
own all decisions, OrganizePlanner owns safe paths/conflicts, and OrganizerExecutor remains the only
mutation boundary. Each batch item is isolated so metadata, classification, conflict, or execution
failure does not stop later files. Scanner progress is forwarded to the caller.

`OperationHistoryRepository` is a domain port. The initial JSON Lines infrastructure adapter is
append-only, Unicode-safe, thread-safe within a process, and persists identifiers, timestamps,
source/destination, operation/status, provider ID, title, and error. Unified workflow Logger events
cover scan, parse/recognition, metadata/candidate outcome, naming/classification, planning, and
execution without secrets.

Phase 13.2 makes discovery configuration-driven. `ResourceLibraryScanner` iterates every enabled
ResourceLibrary and invokes the existing Scanner port; it never branches on Local/OpenList/SMB/S3
types and streams ready discoveries to the organizer callback. `MediaLibraryResolver` converts a
ClassificationResult media-library ID into the configured MediaLibrary and Storage port before
planning.

Runtime ResourceLibrary `storagePath` is the only scan root. Optional `displayRootPath` associates
an explicit host path with a library for compatibility commands; legacy ResourceLibrary `rootPath`
is accepted as its alias. Omitting both does not affect no-path scan/preview/organize.

`OrganizePlan` now additionally carries portable `StorageLocation` values for source and
destination (`storage_id` plus a strictly relative logical path). Legacy display `source`/`target`
fields remain for compatible output, but Executor prefers storage locations and therefore has no
local absolute-path dependency. This supports Local↔Local, Local↔OpenList, and
OpenList↔OpenList through the existing Storage transfer behavior.

The final CLI commands `scan`, `preview`, and `organize` require no path. They process all enabled
configured ResourceLibraries; legacy explicit-path forms remain compatible. Scan and preview are
read-only, organize remains DryRun unless `--execute` is present, and each file failure is isolated.

## Persistent runtime boundary

Phase 14 wires production CLI scanning to `SQLiteFileIndexRepository` and adds a versioned
`SQLiteTaskRepository` for Task, TaskItem, normalized ResultRecord, and file-operation locks. Both
adapters share the configured database but own separate tables and ports. Config validation never
opens the database; developer `strategy-test` retains an isolated in-memory index.

`PersistentTaskCoordinator` surrounds `MediaOrganizerService` and owns no parsing, recognition,
metadata, naming, classification, planning, or execution decisions. Results are persisted before
terminal item state. Recovery also excludes items with a persisted successful, DryRun, or skipped
result if a crash left their item row active.

Locks are atomically keyed by `StorageID + normalized Storage-relative source path`. Completion
releases them. Explicit resume/retry reclaims only locks owned by the selected stale task and then
creates a new auditable task. Execution requires prior authorization plus a fresh `--execute`.

Phase 20.4 adds a durable `pause_requested` flag and PAUSED Task/TaskItem states. The foreground
workflow polls only at Scanner/media-item boundaries; an already-entered pipeline or
OrganizerExecutor call completes normally. Acknowledgement converts unfinished known items to
PAUSED and releases Task locks. Explicit resume creates a new auditable continuation with the same
scope/limit, retries paused/retryable items, rescans that scope for work not yet discovered, and
filters persisted successful/DryRun/skipped results.

Pause is not cancellation, rollback, forced interruption, claim loss, automatic retry, or execution
authorization. It does not alter Automation Job claim fencing, and an organize continuation requires
both original execute authorization and a fresh `--execute`. Distributed Task leases and automatic
crash replay remain deferred. See [`docs/roadmap.md`](roadmap.md).

Phase 20.5 adds `WorkflowRetryController` around only the read-only
`StrategyTestRunner.run_path` boundary. Its validated policy is disabled by default and uses bounded
exponential backoff only for normalized timeout, connection, rate-limit and provider-unavailable
categories after adapter/provider-local attempts are exhausted. Pause/cancel is checked before each
attempt and in bounded wait slices. Evidence contains only stage, next attempt, category and delay;
SQLite schema v16 persists retry count and final category. Planner, conflicts, duplicate/attachment
reads and OrganizerExecutor are outside the controller, so Storage mutations and uncertain outcomes
are never automatically replayed.

Phase 20.6 carries normalized ResourceLibrary `storagePath` into `OrganizePlan` solely as an
exclusive source-cleanup boundary. `DirectoryCleanupPolicy` defaults to NONE. After attachments and
the primary MOVE are fully verified, OrganizerExecutor may inspect a bounded number of source
ancestors. EMPTY deletes only a freshly re-listed empty directory; IGNORABLE validates the entire
bounded listing as ordinary files with explicit safe basename patterns, stats every entry, deletes
only those files, re-lists, then deletes the empty directory. It never reaches the configured library
root or Storage root, follows a link, invokes recursive deletion, touches a destination, or runs for
DryRun/COPY/LINK/failure/rollback. Unknown content stops safely; a Storage/race failure after the
successful MOVE yields PARTIAL evidence. SQLite schema v17 persists cleanup status and step count.

Phase 21.0 introduces a durable manual RecognitionType decision before metadata. A tracked
UNRECOGNIZED result creates one bounded `RecognitionReview`, snapshots only enabled configured
types, transitions the TaskItem to WAITING_RECOGNITION and releases its source lock. CLI resolution
atomically records the selected snapshot type plus actor/note audit and returns the item to PENDING.
Explicit Task resume loads `RecognitionSelection`; `StrategyTestRunner` accepts it only when the new
rule-engine result is still UNRECOGNIZED and the configured type remains enabled, then constructs a
visible `manual-review` RecognitionResult and uses the normal policy resolver. It does not mutate a
RecognitionRule or configuration and has no hidden A fallback. SQLite schema v18 owns review,
choice and audit tables. Review commands do not construct Storage or providers.

## Attachment file sets

Phase 16 adds `AttachmentDiscovery` as a read-only application service after the primary media has
completed strategy resolution. It lists only the primary file's containing directory through the
source Storage port; Scanner traversal, Parser, Naming, and metadata behavior remain unchanged.
The result is an immutable `MediaFileSet` containing typed `MediaAttachment` records.

`AttachmentPlanner` derives safe Storage-relative destinations from the already-produced
NamingResult and appends immutable `AttachmentPlan` entries to OrganizePlan. Subtitle locale and
Forced/SDH/HI suffixes are retained; NFO follows the named primary stem; poster/fanart keep
conventional names; related images and trailers remain in the named media directory. All targets
are preflighted for collisions before execution.

OrganizerExecutor executes attachment plans before the primary media and records every completed
step. This ordering normally leaves the primary at source if a sidecar fails. Runtime failures can
still produce PARTIAL; SQLite ResultRecord schema v3 persists completed-operation evidence and the
attachment count for explicit recovery. There is no recursive cleanup, content read, NFO parsing,
image download, fallback, or implicit overwrite.

## Important interfaces

Phase 17 completes RuntimeConfiguration construction for SMB and the normalized S3 variants
(`s3`, `r2`, and `s3-compatible`) using the existing infrastructure adapters. JSON stores only
environment-variable names; values are resolved at adapter construction and remain redacted.
Configuration validation uses secret placeholders only inside immutable config value objects and
does not contact Storage.

`mediaflow storage list` renders configured identity and declared capabilities without adapter
construction. `storage check` constructs only selected adapters and invokes existing health checks
or a root listing. Failures are isolated, and no write probe is permitted.

## Phase 18.1 service boundary

The first service adapter is a versioned WSGI API over application/repository ports. It reads
persistent Task, Result, Confirmation, and AutomationJob state without constructing Storage. A
bearer token is resolved from a configured environment-variable name at server startup and compared
with a timing-safe operation; authorization data never enters responses or persisted errors.

AutomationJob is a durable request to start an existing `scan` or `preview` workflow, separate from
the media Task lifecycle. SQLite schema v4 atomically claims the oldest pending job. The Worker owns
no Scanner, strategy, planner, or executor logic: its injected production handler invokes the
existing workflow entry point, which creates normal Task and Result records. Pending cancellation is
terminal immediately; Phase 18.2 additionally makes running cancellation cooperative between items.
The service accepts no organize/execute job, so preview preserves DryRun's zero-
mutation boundary. Scheduler, Webhook, notifications, protected remote execute, and the minimal
operator Web UI are implemented in later phases; production identity/TLS remain external work.

## Phase 18.2 automation loop

SQLite schema v5 adds durable cancellation requests, schedule provenance, and next-run state.
Pending cancellation is terminal immediately; a running request is observed by Worker and passed
into ResourceLibraryScanner/MediaOrganizerService. Discovery stops before another item begins while
an in-flight provider or Storage read may finish. Strategy engines and adapters remain unaware of
Task control.

The resident Worker claims one job at a time, sleeps for a bounded configured interval when idle,
and stops gracefully on SIGINT/SIGTERM. Stale running jobs are never silently retried; inspection
and age-guarded requeue are explicit operator actions.

IntervalScheduler atomically persists each scan/preview occurrence and next-run timestamp. Restart
or repeated ticks cannot duplicate an occurrence; missed intervals are coalesced, not backfilled.
Scheduler creates queue records only and never calls Scanner, Storage, Metadata, or Executor.

Phase 19.17 exposes only this existing cancellation use case in the operator UI. Job detail gates the
control to pending/running states and requires Request then Confirm; Keep only removes the local
confirmation prompt. The final POST has an empty body/query and remains protected by `CANCEL_JOB` plus normalized
security audit. JavaScript does not infer or persist a new status, and terminal state is always
reloaded from the API. This UI boundary constructs no media service and adds no submission, Task
control, retry/resume, execute authority, rollback, or Storage mutation.

Phase 19.18 exposes the existing `AutomationJobService.submit` boundary without adding a workflow.
The operator UI constructs an immutable allowlisted payload only after Open, Review, and Confirm;
Back/Keep sends nothing. The API accepts exactly scan/preview plus an optional 1–10000 limit, while
the separately authorized remote-organize branch remains inaccessible from the UI. Queueing writes
only the durable Job and security audit. Storage/provider/scanner/workflow construction happens only
if a later Worker claims the Job, under the existing DryRun and cancellation boundaries.

Phase 19.19 adds one durable active-Job admission rule shared by manual DryRun, Scheduler, and protected
remote organize. `maximumActiveJobs` counts Pending/Running only. SQLite uses `BEGIN IMMEDIATE` to
serialize count-plus-insert across repository connections; terminal rows remain historical but no
longer consume capacity. The ordinary `create_job` method remains only for migrations/test fixtures,
while every production submission path calls an admission-aware transaction.

Phase 19.20 adds a separate read-only stale observation path. SQLite filters Running rows by the
configured age cutoff, orders by `(updated_at, job_id)`, and applies the 1–100 limit in SQL. The API
returns only safe job identity/state fields; the UI loads it explicitly and offers no recovery
action. Staleness is deliberately not a lease or liveness proof. Execute-authorized organize Jobs
are highlighted because replay after an uncertain mutation can be unsafe.

Phase 19.21 adds repository-enforced claim ownership. Each Pending → Running transition receives a
new opaque random token; heartbeat and terminal writes require both Running status and that token.
Requeue clears ownership, so an old Worker cannot refresh or complete over a later claim and cannot
publish that claim's terminal notification. Tokens are structurally excluded from transports and
operator output. The Worker invokes heartbeat through the existing cooperative cancellation callback
before/between items and after handler return; it deliberately has no background thread. Blocking
external calls can therefore still outlive the observation threshold, and recovery UI remains blocked.

Scheduler checks capacity in the same transaction as conditional state advance, Job insert, and audit;
full capacity rolls back all three. Execution authorization checks capacity before its atomic token
consume/Job/audit transaction, so queue-full cannot burn a ticket. API maps the stable domain rejection
to audited HTTP 409. None of these admission paths constructs or calls a media service.

## Phase 18.3 Cron and schedule audit

CronExpression is a bounded pure-domain parser/evaluator for five numeric fields. It accepts only
wildcards, lists, ranges, and steps and never invokes a shell or external cron daemon. Calendar
evaluation uses standard-library `zoneinfo`, persists UTC instants, skips nonexistent DST wall
times, and selects fold 0 once for an ambiguous wall time. Restricted day-of-month and day-of-week
use OR semantics.

Runtime schedules are a validated union: exactly one of intervalSeconds or cron/timezone. Conditional
SQLite state advancement prevents concurrent duplicate emission and missed occurrences coalesce.
Schema v6 adds append-only schedule audit with occurrence, emission, Job, command, and next-run
identity. CLI/API audit reads construct no Storage or provider adapters.

- `Storage` exposes read/write concepts and explicit capabilities. Business logic targets this
  protocol rather than filesystem APIs.
- `Scanner` and `Parser` are read-only/local-information boundaries.
- `RecognitionRule` returns only a `RecognitionResult`.
- `MetadataProvider` returns internal `MediaCandidate` and `MediaIdentity` models; provider DTOs
  cannot leak into business logic.
- `NamingPolicy` computes names; `ClassificationPolicy` computes a media library and relative path.
- `OrganizePlanner` builds immutable plans and may use only the read-only `Storage.exists` query
  for conflict observation. `OrganizerExecutor` remains the application mutation boundary.

## Safety boundaries

- Scan, parse, recognition, metadata, naming, classification, and planning do not mutate storage.
- Dry run generates and displays an `OrganizePlan` without calling the executor.
- Only `OrganizerExecutor` calls mutating Storage methods.
- LocalStorage confines paths to its root and never overwrites by default.
- Cross-storage COPY/MOVE are explicit Executor paths: they stream through Storage ports, verify
  the target, and delete the source only for MOVE after verification. Cross-storage links and
  implicit operation fallbacks fail explicitly.
- Delete and overwrite require future explicit policy authorization; the planner emits neither.
- No FFmpeg or FFprobe dependency exists. Technical tags remain filename/path observations.

## LocalStorage adapter

`LocalStorage` is configured with a storage ID, display name, root directory, and read-only flag.
Callers use portable logical paths relative to the configured root; absolute paths are rejected.
The adapter normalizes `.` and repeated separators, rejects traversal above the root, and resolves
existing symbolic links before access so a link cannot provide access outside the root.

Write and copy stage into a unique operation-owned file in the target directory, flush the stage,
then publish it with an atomic same-filesystem namespace operation. No-overwrite uses atomic link
creation; overwrite uses atomic replace. Failures remove only the stage and preserve any old target.
This is target-visibility atomicity, not power-loss durability or a multi-file transaction.

Directory and stat results use `StorageEntry`, including name, logical path, entry type, size, and
UTC modification time. Reads return binary streams. Writes accept bytes or a binary stream; stream
copying and filesystem-native copy avoid loading an entire media file into memory. Parent
directories are not created implicitly by file operations and must be created through
`create_directory`.

All adapter failures exposed to callers are `StorageError` values with stable codes and an optional
original cause. Existing targets produce `ALREADY_EXISTS` unless overwrite was explicitly passed.
Delete removes files, links, or empty directories only and never recursively deletes a directory
tree. Hard and soft links never fall back to copy or move; unsupported platforms return
`UNSUPPORTED_OPERATION`.

Read-only storage permits list, stat, exists, read, and no mutations. Its mutation capabilities are
reported as false. Writable capability reporting also checks whether the running platform exposes
hard-link and symbolic-link primitives.

## SMBStorage adapter

`SMBStorage` implements the same domain `Storage` protocol through an infrastructure-only
`SMBClient` boundary. Production uses the optional `smbprotocol` package's high-level `smbclient`
API; unit tests inject a fake client and never require a NAS. SDK sessions, directory entries, and
exceptions do not cross the adapter boundary.

The configuration contains host, port, share, credentials, optional domain, logical root path,
read-only state, connect/operation timeouts, and maximum concurrency. Its representation always
redacts the password. Business paths remain relative: the adapter rejects absolute, drive, UNC,
other-share, and above-root paths before contacting the client, then prefixes the normalized path
with the configured root inside the selected share.

Connections are established lazily and reused by the production client's connection cache until
explicit close. A bounded semaphore limits concurrent operations; returned read streams retain a
permit until closed. Connect and operation calls have configured deadlines. On connection loss,
only read-only/idempotent operations reconnect once; mutating operations are never blindly
retried. Timeout abort attempts close the cached client connection and return a unified timeout
error.

List results are converted to domain `StorageEntry` objects from metadata already returned by SMB
`scandir`; this avoids an unbounded second stat request and preserves configured non-default ports.
Explicit stat, read, write, and same-share copy use the configured port and the latter three stream
in one MiB chunks. Move uses native SMB rename/replace and never falls back to copy plus delete.
Delete handles files and empty directories but is not recursive. HardLink and SoftLink are
deliberately unsupported, report false capabilities, and never fall back to another operation.

SMB client failures map to domain Storage error codes for missing paths, permissions, conflicts,
connection failure/loss, authentication, timeout, I/O, and unknown errors. Public messages contain
only the operation and error category, not credentials or arbitrary SDK exception text. Standard
`OSError`/`SMBOSError` errno values are classified structurally (`ENOENT`, `EEXIST`, `EACCES`/`EPERM`,
timeout, and connection errno families); message parsing is not used.

Phase 19 endurance acceptance is implemented as a separately gated test boundary, not a runtime
workflow or retry service. It drives the production adapters and `OrganizerExecutor` with bounded
generated streams, observes the actual source-stream read size, injects one deterministic read
failure, inspects source and target state, and performs a new explicit retry. The harness never loads
runtime configuration. A partial target may be deleted only because its random run path is
allowlisted inside a preflight-proven empty acceptance root; production does not gain automatic
cleanup, rollback, or retry semantics from this test.

## OpenListStorage adapter

`OpenListStorage` implements `Storage` behind an infrastructure-only `OpenListClient`. Configuration
contains an HTTP(S) base URL, opaque token, logical OpenList root, read-only state, connect/request
timeouts, pagination size, bounded concurrency, and bounded idempotent retry settings. Tokens are
sent in the `Authorization` header exactly as OpenList v4 expects and are redacted from configuration
representations and public errors. OpenList JSON/HTTP types never leave infrastructure.

The API contract was verified on 2026-08-19 against the official OpenList v4 `main` sources and the
official documentation published as v4.2.4. The adapter uses `GET /ping`; `POST /api/fs/list`
(`path`, one-based `page`, `per_page`, `refresh`, returning `content` and `total`);
`POST /api/fs/get` (including `raw_url`); `POST /api/fs/mkdir`; `POST /api/fs/rename`;
`POST /api/fs/move`; `POST /api/fs/copy`; `POST /api/fs/remove`; and streaming
`PUT /api/fs/put` with URL-encoded `File-Path`. Sources:
[official documentation](https://doc.oplist.org/),
[read handlers](https://github.com/OpenListTeam/OpenList/blob/main/server/handles/fsread.go),
[management handlers](https://github.com/OpenListTeam/OpenList/blob/main/server/handles/fsmanage.go),
and [authentication middleware](https://github.com/OpenListTeam/OpenList/blob/main/server/middlewares/auth.go).

Business paths are normalized once, remain Unicode logical paths relative to the configured root,
and reject absolute paths, URLs, drives, NULs, and traversal before any request. List exhausts the
server's finite pages. OpenList v4.2.2 represents an empty directory with `content: null` and
`total: 0`; the adapter normalizes only that internally consistent pair to an empty page. Null with a
non-zero total, invalid totals, and other non-list content remain invalid responses. Reads follow the
`raw_url`/proxy/redirect choice made by OpenList and expose a
stream; uploads pass a chunk iterator and never buffer a whole media file. Returned streams retain a
concurrency permit until closed.

Native Copy/Move are used within one OpenList configuration when the basename is preserved.
Copy with a new basename uses a streaming Read-to-Upload fallback and keeps the source.
Same-directory Move name changes use Rename. A Move that changes both directory and basename uses
two native server-side operations: first Move with the original basename, then Rename in the target
directory. If Rename fails, the adapter attempts to move the intermediate file back to its original
location. A failed rollback reports an I/O error and leaves the file at the explicit intermediate
path; this flow never downloads/uploads the media through MediaFlow.
Delete checks directory
contents first and never invokes OpenList's potentially recursive remove for a non-empty directory.
HardLink and SoftLink are unsupported. Mutations are never automatically retried; only read-only,
idempotent calls retry bounded temporary connection, timeout, 429, and 5xx failures, respecting a
bounded `Retry-After` delay.

## S3 / R2 Storage adapter

`S3Storage` is one infrastructure adapter for AWS S3, Cloudflare R2, and generic S3-compatible
services such as MinIO or Ceph. `S3Provider` selects compatibility defaults while endpoint, region,
and path-style addressing remain configuration choices. Cloudflare R2 defaults its SDK region to
`auto`; AWS defaults to `us-east-1` when no region is supplied. Production uses the optional
`boto3`/botocore SDK behind an infrastructure-only `S3ClientAdapter`; SDK responses and exceptions
do not cross into domain models.

Storage-relative paths map to one configured bucket and normalized `RootPrefix`. Absolute paths,
S3 URLs, bucket-like paths, drives, NULs, and traversal above the prefix are rejected locally.
Directory semantics are deliberately logical: `CreateDirectory` creates a zero-byte trailing-slash
marker, while Stat/List also recognize implicit directories when objects exist below a prefix.
List uses delimiter `/`, consumes every continuation page, merges common prefixes with direct
objects, and hides marker objects from callers. Deleting a non-empty prefix is always rejected;
an empty implicit directory without a marker is not mutated because there is no object to delete.

Reads return the SDK streaming body and retain a concurrency permit until closed. Small writes use
streaming `PutObject`. Objects at or above the configured multipart threshold use explicit create,
bounded-size part upload, complete, and best-effort abort on any part or completion failure. The
adapter never materializes an entire input stream. Copy uses server-side `CopyObject`, preserving
the source. Objects over the configurable single-copy ceiling return UnsupportedOperation because
multipart UploadPartCopy is not implemented in this phase; there is no client-memory fallback.

S3/R2 Move is an emulated operation:

1. Verify the target does not exist.
2. Copy the source to the target.
3. Verify the target exists and has the source size.
4. Delete the source.

The operation is not atomic. If step 4 fails, both source and target may exist, and the adapter
returns a partial/ambiguous `IO_ERROR`, never success. Copy or verification failure never deletes
the source. ETags are not treated as MD5 because multipart and compatible providers have different
ETag semantics.

Read-only/idempotent List, Stat, Exists, Read, and health calls receive bounded retries for timeout,
connection loss, rate limiting/SlowDown, and selected 5xx conditions. `Retry-After` is bounded.
Adapter mutations are not blindly retried, and botocore automatic attempts are limited to one.
Connect/read timeouts and SDK connection pools derive from configuration; adapter-level operations
use a bounded semaphore. Credentials, session tokens, authorization data, and signed URLs are not
logged or included in public errors.

Writable S3/R2 reports Move, Copy, and Delete support. Move means the non-atomic emulation above.
HardLink and SoftLink are unsupported and never fall back. The current domain capability model does
not expose atomicity as a separate flag; this documented semantic is therefore part of the adapter
contract. Range reads and presigned URLs are deferred because the current Storage protocol has no
range-read operation and direct streaming requires neither.

## ResourceLibrary, Scanner, and FileIndex

`ResourceLibrary` is configuration describing one discovery scope: a Storage ID, storage-relative
root, enabled state, full/incremental mode, maximum depth, bounded scan concurrency, include and
exclude rules, configurable media extensions, persistence batch size, and file stability policy.
It contains no movie/TV identity, parser, metadata, naming, classification, or organization logic.
Rules support path, filename, extension, directory, glob, and regex matching. Configured excludes
have priority and prune matching directories before further List calls. Default rules cover common
temporary/download files and system directories but can be replaced by configuration.

`StorageScanner` depends only on the domain `Storage` protocol and `FileIndexRepository`; it has no
imports or branches for LocalStorage, SMBStorage, OpenListStorage, or S3Storage. A read-only Storage
is valid. The scanner calls only Stat and List. It never calls Read for media contents and never
calls Write, CreateDirectory, Move, Copy, Delete, HardLink, or SoftLink. This no-mutation boundary is
locked by a fake Storage acceptance test that fails on any mutation invocation.

Traversal starts at depth zero. `max_depth=0` processes root files only, `1` additionally processes
direct child directories, and `None` is unlimited. Directory symlinks and all other non-file entry
types are not followed. A bounded executor limits concurrent directory List operations; concrete
Storage adapters retain their own lower-level concurrency limit. Only a bounded number of directory
results are in flight, discoveries are emitted through an optional callback, and FileIndex writes
are flushed in configured batches rather than accumulating the complete library in ScanResult.
Cancellation stops scheduling new List calls, preserves already persisted discoveries, produces
Cancelled, and never performs Missing reconciliation. One in-process lock per ResourceLibrary
prevents duplicate concurrent scans.

FileIndex identity is `(storage_id, resource_library_id, path)`, so overlapping libraries remain
separate records. `ResourceLibraryService.overlapping_pairs` reports same-storage overlapping roots
for configuration warnings; overlap is permitted because library identity is explicit. The
repository port provides lookup, batch upsert, per-library listing, and scan-generation-based
Missing reconciliation. A thread-safe in-memory adapter supports tests and a durable SQLite adapter
uses batch transactions and a uniqueness constraint.

Incremental state uses only path, size, and modification time: New, Modified, or Unchanged. No media
hash is calculated. Full scans mark unseen prior records Missing and retain `missing_since`; they do
not delete history. Failed and Cancelled scans never reconcile Missing. Partial scans protect every
failed or deliberately pruned prefix, so inaccessible or out-of-scope subtrees keep their previous
states while successfully covered subtrees can still reconcile safely.

Stability is evaluated across scans without sleeping. Minimum file age compares scan time with
StorageEntry modification time. When size and modification time remain unchanged, `stable_since`
starts at the prior observation time and progresses across scans. Either change resets it. A file is
Ready only after both minimum age and configured stable duration are satisfied; otherwise it is
Unstable. Scanner output contains filenames and basic storage metadata only—no title, year, season,
episode, TMDB identity, or technical stream inspection.

`ScanResult` and `ScanTask` expose indeterminate count-based progress: directories/files visited,
candidates, ignored files, unstable files, and errors. Root access/list failures produce Failed.
Child directory failures are recorded as structured ScanError values and produce PartialSuccess
while other directories continue.

## Local media parsing

`MediaParserService` is a pure application service over the existing domain `FileContext`. It
combines `FilenameParser` and `PathParser` without reading Storage, writing FileIndex, opening a
network connection, or inspecting media streams. `FilenameNormalizer` preserves the original name
while normalizing separators, brackets, and Unicode whitespace for deterministic rule matching.

Filename rules extract candidate title/year, explicit season and episode markers, bounded
multi-episode ranges, resolution, release source, video/audio tags, channel layout, HDR/version,
language, release group, extension, and uninterpreted raw tags. Path rules use supplied parent
directory names for title/year and explicit season-directory evidence. Filename evidence has
precedence; conflicting directory evidence is retained as an alternative plus a structured warning.
Evidence carries source and simple confidence only; it is not metadata candidate scoring.

Regex rules are compiled and range expansion has a configurable upper bound. Malformed markers
produce warnings and invalid filenames produce typed parser errors. Parsing returns candidates
only: it does not infer media identity, RecognitionType, provider identity, naming, classification,
or an organize target.

Phase 20.1 adds NFO as a third, explicitly bounded local evidence source. `NfoParser` is a pure XML
parser over supplied bytes/text. It rejects DTD/entity declarations, unsupported roots, malformed
XML, and configured byte/depth/element/text/ID/episode limits. It normalizes common movie, TV show,
and episode title/year/season/episode plus provider/external-ID evidence into domain Parser types;
provider DTOs and `MediaIdentity` are not created here.

`StorageNfoEnricher` is the only NFO I/O orchestration. It lists one media directory through the
provider-neutral Storage port, deterministically prefers `<media-stem>.nfo`, then `movie.nfo`, then
`tvshow.nfo`, and performs at most one bounded read. Missing NFO is a no-op; read or parse failures
become bounded Parser warnings. Valid NFO semantic evidence takes precedence while conflicting
filename/path values remain warnings and alternative candidates; technical release tags remain
filename-derived. Strategy and organizer flows opt into enrichment only when both configured
Storage identity and Storage-relative source path are available. Synthetic paths preserve the old
filename/path-only behavior. No NFO write/generation, recursive discovery, network request, or
Storage mutation is part of this boundary.

## Recognition rules and type policies

`RecognitionRuleEngine` is a deterministic, pure application service over `RecognitionContext`,
which contains the existing `FileContext` and `ParseResult`. It does not parse filenames again and
has no Storage, database, Metadata Provider, HTTP, naming, classification, or organizer dependency.
Recognition only selects a configured `RecognitionType` ID.

Rules contain immutable AND/OR/NOT/ALWAYS condition trees. Atomic conditions cover filename,
normalized storage-relative path, parent directory names, extension, parser candidate fields, and
ResourceLibrary ID. String comparisons are case-insensitive by default; numeric and collection
operators are type-validated. Regexes compile when conditions are created. Patterns are capped at
256 characters, common catastrophic nested quantifiers and backreferences are rejected, and match
input is capped at 4096 characters because the Python standard regex engine has no timeout.

Enabled rules run by priority descending and then rule ID ascending, providing stable ordering.
`stop_on_match` stops lower ordered rules. Matching rules for one type aggregate their scores.
Across types, the highest matched priority wins, aggregate score breaks an equal-priority tie, and
an exact tie returns `Ambiguous` without a selected type. No match returns `Unrecognized`; there is
no implicit default. Results retain matched rules, alternatives, machine-readable reasons, and
field/operator evidence.

`RecognitionTypePolicyResolver` validates one enabled type-policy mapping per RecognitionType and,
when policy catalogs are supplied, rejects missing or disabled Metadata, Naming, Classification,
and Organize policy references. It returns policy IDs only and never executes a policy. The four
references are independent and reusable. In particular, C maps to Metadata C plus Naming A,
Classification A, and Organize A while the resolved `recognition_type_id` remains C.

## Metadata providers, matching, and TMDB

The domain `MetadataProvider` port exposes capability-described movie/TV search and details,
season/episode details, and external-ID lookup. `MetadataProviderRegistry` resolves providers by
opaque ID, while `MetadataPolicy` selects media query type, locale, thresholds, cache/retry policy,
candidate/page limits, a per-identification request budget, and a bounded candidate-enrichment
limit (default 2). Application code contains no TMDB HTTP or DTO knowledge.

`MetadataIdentificationService` receives an already resolved `RecognitionResult`; metadata never
selects or rewrites a RecognitionType. It searches through the configured provider, delegates all
selection to `CandidateMatcher`. When search fields cannot establish a title match and the provider
advertises alternative-title support, it may enrich only a bounded set of media-type-compatible,
exact/near-year candidates, then rescore. Search rank breaks enrichment ties; the existing request
budget and details cache still apply, and an enriched detail response is reused after selection.
Year controls which candidates are economical to enrich but never becomes sufficient match
evidence. TV episodes are verified from one season response. Multi-episode order is retained.
Missing episodes return
`MetadataMismatch`. Direct provider-ID confirmation bypasses text search. Every successful
`MediaIdentity` copies the input RecognitionType ID, so C remains C.

`CandidateMatcher` is pure and deterministic. It scores the best pairing across parser primary/
alternative title candidates and provider display/original/translation/alternative titles. The
source remains `title`, `original_title`, `translation`, or `alternative_title`. Unicode
NFKC/casefold/punctuation-tolerant title similarity contributes up to 65 points, exact/near year
contributes up to 20, compatible media type
5, and agreeing parser title evidence 10. Large year mismatches subtract 15. Provider popularity is
retained but never scored. Candidate ordering uses score, exact-title, exact-year, then provider ID.
Each score records the winning local title, provider title, provider-title source, and exact or
similarity reason so strategy-test can explain localized matches.
The defaults are automatic at 90, confirmation at 70, and a minimum top-two gap of 5; a smaller gap
is `Ambiguous`, and the first search item has no special status.

Movie date semantics distinguish canonical identity dates from regional presentation dates.
`MediaCandidate.year`/`canonical_year` and `canonical_release_date` are the canonical values used by
year scoring. `regional_release_date`/`regional_year` are displayed as zero-point informational
evidence and never replace the canonical identity year. When movie search uses a region, its
returned `release_date` is normalized as regional rather than canonical. Bounded detail enrichment
then supplies the canonical movie-details `release_date` before final scoring. A filename using a
regional re-release year therefore does not silently redefine the movie identity. TV keeps its
separate canonical `first_air_date` semantics and does not use movie regional-date handling.

`MetadataCache` stores normalized candidates and identities rather than raw TMDB responses. Keys
include provider, operation, query/ID, year, language, region, season, and episode as applicable.
Search, detail, and short negative TTLs are independently configured; `force_refresh` bypasses
reads. Errors are never cached.

The TMDB infrastructure adapter was verified on 2026-08-19 against current official documentation:
[application authentication](https://developer.themoviedb.org/docs/authentication-application),
[movie search](https://developer.themoviedb.org/reference/search-movie),
[movie details](https://developer.themoviedb.org/reference/movie-details),
[movie translations](https://developer.themoviedb.org/reference/movie-translations),
[movie alternative titles](https://developer.themoviedb.org/reference/movie-alternative-titles),
[region support](https://developer.themoviedb.org/docs/region-support),
[TV search](https://developer.themoviedb.org/reference/search-tv),
[TV details](https://developer.themoviedb.org/reference/tv-series-details),
[append to response](https://developer.themoviedb.org/docs/append-to-response),
[season details](https://developer.themoviedb.org/reference/tv-season-details),
[episode details](https://developer.themoviedb.org/reference/tv-episode-details),
[find by external ID](https://developer.themoviedb.org/reference/find-by-id), and
[rate limiting](https://developer.themoviedb.org/docs/rate-limiting).

It uses read-only v3 GET endpoints and the API Read Access Token as a Bearer Authorization header.
Movie search sends query, optional primary release year, language, region, page, and adult=false.
If the strict primary-year search is empty, one bounded relaxed pass omits the year while retaining
the other policy parameters.
TV search uses query, optional first-air-date year, language, page, and adult=false. Region is not
sent to endpoints that do not document it. Find validates the documented external-source names.
TMDB JSON is converted immediately into domain candidates/identities. Detail enrichment appends
translations, alternative titles, and external IDs in one request; translation DTOs become the
provider-neutral `translated_titles` field and never reach CandidateMatcher.

Connect/request timeouts, a bounded semaphore, retry count, exponential delay, maximum delay, and
an injectable sleeper are configuration-driven. Only connection/timeout, 429, and selected 5xx
failures retry. `Retry-After` is honored within the configured maximum. The official legacy fixed
limit is disabled and current upper limits may change, so no fixed QPS is hardcoded. Authentication,
permission, not-found, rate-limit, timeout, connection, unavailable, malformed, unsupported, and
unknown errors map to `MetadataError`. Tokens are redacted from configuration representations and
never included in public errors.

## Strategy test CLI

`strategy-test` is a developer-only adapter over the existing application pipeline. It creates a
synthetic `FileContext` from a supplied path, then calls the production `MediaParserService`,
`RecognitionRuleEngine`, `RecognitionTypePolicyResolver`, and optionally
`MetadataIdentificationService`. It displays parser evidence/warnings, recognition evidence and
priority, resolved policy IDs, candidate score components, match status, and final identity. It
does not implement parsing, recognition, policy resolution, or candidate scoring itself.

The built-in smoke configuration supplies explicit A/B/C path rules and mappings A→A/A/A/A,
B→B/B/B/B, and C→C/A/A/A. These are test defaults, not production configuration. Single-path mode
is offline by default; `--offline` is explicit, and `--live-metadata` constructs the existing TMDB
adapter only when `TMDB_ACCESS_TOKEN` (or local alias `TMDB_TOKEN`) is present. Tokens and Bearer
headers are redacted from CLI errors.

The development policy data lives in the infrastructure bootstrap
`development_strategy_configuration`, separate from parsing, recognition, and metadata domain
logic. It explicitly configures MetadataPolicy A (TMDB movie), B (TMDB TV), and C (TMDB movie),
including matcher thresholds and optional `TMDB_LANGUAGE`/`TMDB_REGION`. `MetadataPolicyRegistry`
is the application catalog used by both offline display and live identification. Before a directory
scan begins, `StrategyTestRunner.validate_configuration` verifies every enabled
RecognitionTypePolicy → MetadataPolicy reference and, for live mode, every MetadataPolicy →
MetadataProvider reference. Global faults are reported as `ConfigurationError` and never attributed
to an individual media file. Offline validation requires configured policies but no provider,
network, or token.

Case-file JSON is read only at the CLI boundary. The application runner receives decoded data and
may use an in-memory `MetadataProvider` fixture while still exercising the production metadata
service and matcher. Expectations are optional per field; failures include expected/actual results
and recognition evidence. The starter corpus covers A/B/C, C policy reuse, exact/wrong-first/low/
ambiguous/no-result metadata, TV single/multi-episode, Unicode, and directory conflicts.

`ReadOnlyStrategyStorage` delegates reads and advertises no mutation capabilities. Every mutation
method increments an audit counter and immediately raises `StrategyMutationError`; the runner also
verifies all counters remain zero. Naming, Classification, OrganizePolicy, and OrganizerExecutor
are never invoked—their IDs are display-only.

Directory mode is a local developer adapter that constructs `LocalStorage(read_only=True)`, wraps
it in `ReadOnlyStrategyStorage`, and supplies it to the production `StorageScanner` with a minimal
`ResourceLibrary` and ephemeral in-memory `FileIndex`. Scanner therefore owns traversal,
extension/exclusion filtering, concurrency, and cancellation. Each ready discovery enters the same
single-path strategy runner. `--limit` cancels scanning after the requested number of strategy
items, and metadata remains offline unless `--live-metadata` is explicit. The FileIndex is
ephemeral process state; no user files or persistent database are modified.

## Naming policies and engine

Naming is a pure application calculation over an already resolved `MediaIdentity`, `ParseResult`,
RecognitionType ID, and `NamingPolicy`. `NamingContext` carries those inputs without provider,
Storage, Classification, or Organizer services. `NamingResult` contains only relative directory
components, a filename, policy/type identity, rendered-variable evidence, warnings, and
sanitization changes. It contains no MediaLibrary or final destination path.

`NamingPolicy` has stable ID and enabled state plus separate movie directory/file, TV series/
season/episode, and multi-episode templates. `NamingPolicyRegistry` rejects duplicate, missing, and
disabled policies and validates every template before use. The strategy development bootstrap
configures policy A for movies and policy B for TV; type C resolves policy A without changing its
RecognitionType C identity.

`SafeTemplateRenderer` is a deliberately restricted placeholder DSL. It supports named fields only
and decimal zero-padding such as `{season:02}`; unknown variables, conversions, expressions,
unclosed fields, unsupported format specifiers, absolute literals, and path separators fail
validation. It does not use `eval`, `exec`, Jinja, shell execution, or another general-purpose
language. Supported metadata fields are title/original title/year/season/episode(s)/episode title/
provider/provider ID. Release observations and extension come only from ParseResult or the original
file context. MediaIdentity year takes precedence, with an explicit warning when ParseResult year is
used as fallback.

For TV, season and episode zero are values rather than missing data. Episode inputs are sorted and
deduplicated. Contiguous `[1,2,3]` renders `E01-E03`; non-contiguous `[1,3]` renders `E01E03`, so a
filename never implies an absent episode. Multi-episode templates omit episode titles by default.
Missing variables follow an explicit Error, Empty, or OmitToken strategy; OmitToken performs
conservative cleanup of empty parentheses/brackets and orphan separators.

`NameSanitizer` normalizes Unicode to NFC, preserves non-ASCII scripts, collapses Unicode
whitespace, removes control and cross-platform-illegal filename characters, strips trailing dots/
spaces, and prefixes Windows-reserved names. Every result is one safe component with no slash,
backslash, absolute path, drive, URI, `.` or `..`. Component limits count Unicode code points. Long
components use deterministic middle truncation to retain the filename extension and a useful tail
such as episode/provider identity; storage-specific byte limits remain future work.

`NamingPreviewService` resolves a configured policy and calls `NamingEngine`; it does not invoke
Classification or Organizer. Naming has no Storage or MetadataProvider dependency, performs no
reads, network calls, conflict checks, or mutations, and cannot create or rename files.

The existing `strategy-test --show-naming` adapter optionally appends Naming Preview after the
production Parser → Recognition → policy resolution → Metadata pipeline. It resolves the configured
NamingPolicy ID and calls `NamingPreviewService`; it does not reimplement naming. Without live
metadata, it reports that MediaIdentity is unavailable and does not manufacture an identity from
parser evidence. Directory mode continues to use `StorageScanner` and its hard read-only Storage
guard, then prints compact preview rows and separate metadata/naming/error totals. Case files may
assert a nested `naming` object and still use fake MetadataProvider candidates through the same
production matcher. CLI safety output reports audited Classification execution counts, zero
Organizer executions, and zero Storage mutations.

## Durable notifications

`NotificationPublisher` converts accepted terminal Automation Job and durable Scheduler emission
events into canonical provider-neutral JSON and persists one idempotent Outbox delivery per enabled
subscription. It performs no network or Storage operation. SQLite v7 atomically claims due
pending/retry deliveries, so concurrent NotificationWorkers cannot claim the same row. A claimed
row has a bounded configured lease. Only an expired `delivering` row can be atomically reclaimed;
reclaim preserves its stable ID/body and increments rather than resets attempts.

The independent `NotificationWorker` resolves environment-owned secrets only at startup and signs
`timestamp + "." + exact body` with HMAC-SHA256. Its injected Webhook transport posts only to
validated HTTPS URLs and does not follow redirects. Success is 2xx; transport/429/5xx failures use
bounded exponential retry; other 4xx and exhausted attempts become dead-letter. Only explicit CLI
requeue can reactivate a dead letter. Persisted and displayed failure information is categorical;
payload bodies and secrets are omitted from CLI/API views. Notification failure never changes Job,
Schedule, Task, plan, execution, or media Storage state.

Delivery semantics are at-least-once: a process can stop after the receiver accepts a POST but
before SQLite records success. A recovered worker therefore may redeliver the same stable
`X-MediaFlow-Delivery`; receivers are responsible for idempotent deduplication by that value.

## One-time remote execution authorization

Remote real execution has two independent gates: ordinary API Bearer authentication and a locally
issued one-time execution token. `ExecutionAuthorizationService` generates 256-bit-class random
tokens and persists only SHA-256 digests with expiry and item bounds. SQLite v8 atomically changes
an active authorization to consumed, appends its audit, and inserts an `execute_authorized`
organize AutomationJob. Concurrent replay therefore creates at most one Job.

The API cannot manage authorizations, rejects body-carried tokens, and requires the separate
`X-MediaFlow-Execution-Token` header plus `execute:true` and an explicit bounded limit. The Worker
adds `--execute` only when both the persisted command is organize and its persisted authority is
true; inconsistent Jobs fail closed. Scheduler remains scan/preview-only. This boundary grants no
overwrite/delete bypass: the existing Task, conflict, Storage capability, plan validation, and sole
OrganizerExecutor mutation boundary remain authoritative.

## Scheduled unattended organization: TARGET V1 (not implemented)

### CURRENT foundation

The CURRENT runtime already provides interval/Cron evaluation, atomic and idempotent schedule
emission, durable AutomationJob claim/cancellation/audit, immutable configuration snapshot pinning,
the Worker-to-existing-Task/TaskItem/Result boundary, independent RecognitionTypePolicy references,
and OrganizerExecutor-only mutation. Runtime schedule definitions and ordinary AutomationJob
submission accept only scan/preview. Protected manual/remote organization instead consumes the
one-time authorization described above and persists only that Job's execute-authorized decision.

CURRENT does not provide one operator-managed Automation Task Definition that combines a bounded
ResourceLibrary/source scope, schedule, enabled state, managed configuration authority and a
persistent scoped unattended execution grant. The TARGET below is V1 product scope, not a claim
about current tables, APIs or Web behavior.

### TARGET V1 responsibility flow

```text
Automation Task Definition
  - ResourceLibrary / bounded source scope
  - schedule / timezone / enabled state
  - managed configuration authority
  - explicit scoped unattended execution authority
        ↓
Scheduler (when to emit which definition)
        ↓
Automation Job (one occurrence)
        ↓
pinned immutable configuration snapshot
        ↓
Worker
        ↓
Task / TaskItem (persistent execution state)
        ↓
Scan → Parse → Recognition → RecognitionType
        ↓
RecognitionTypePolicy
  ├─ MetadataPolicy → MetadataProvider
  ├─ NamingPolicy
  ├─ ClassificationPolicy → MediaLibrary + Storage-relative destination
  └─ OrganizePolicy → Move / Copy / HardLink / SoftLink
        ↓
OrganizePlanner / equivalent Preview
        ↓
scope + authority + capability + conflict + safety validation
        ↓
OrganizerExecutor
        ↓
Result / Log
```

Automation Task Definition is a long-lived operator intent. AutomationJob remains one durable
occurrence, while the existing Task/TaskItem/Result model remains the execution and per-item outcome
model. These objects require traceable identities but not a parallel media-work lifecycle.

Scheduler owns only due-time evaluation and durable occurrence emission. It does not resolve or
copy Provider, NamingPolicy, ClassificationPolicy, MediaLibrary, destination or OrganizePolicy, and
it never invokes Storage. Different RecognitionTypes in one occurrence therefore continue to use
independently resolved policy mappings. Metadata Provider comes from MetadataPolicy, destination
comes from ClassificationPolicy, and operation comes from OrganizePolicy.

Metadata selection continues through the existing Provider abstraction and registry. TMDB remains
the first required V1 production Provider. V1 Provider switching means changing the Provider
reference owned by MetadataPolicy through the managed Draft → Validate/Test → Activate lifecycle;
it is not a Scheduler decision and does not require a second production adapter solely as proof.

Each AutomationJob pins the immutable Active configuration selected at its creation boundary.
Later activation, including a MetadataPolicy Provider switch, applies only to subsequently created
Jobs. A queued or running Job must never silently replace its RecognitionTypePolicy, Provider,
NamingPolicy, ClassificationPolicy or OrganizePolicy from a newer Active snapshot.

### TARGET execution authority and safety boundary

Scheduled unattended authority is persistent, explicitly granted, revocable and bound to exactly
one Automation Task Definition plus its permitted source/run scope. It is separate from the CURRENT
one-shot manual/remote ticket and does not consume a fresh ticket for every due run. It also does
not grant policy selection, Storage capability, Overwrite, Delete, source cleanup, operation
fallback or access beyond the definition's bounds.

Configuration follows Configure → Validate/Test → Preview/DryRun → explicit unattended
enablement → Scheduled Runs. An equivalent zero-mutation Preview remains available, but a valid
grant removes the need for another interactive Preview or Execute click on each occurrence. Every
run still builds a normal immutable plan and validates the pinned snapshot/references, source
scope, live authority, permissions, Storage capabilities, conflicts and all other safety gates.
The authority boundary must be checked before each not-yet-performed mutation so revocation can
stop future effects without rewriting completed effects.

Any missing/invalid pinned revision, broken reference, unavailable Provider, invalid permission,
capability gap, revoked/expanded/mismatched authority, out-of-scope path or unresolved safety
decision fails closed before media mutation and persists actionable Job/TaskItem/Result evidence.
OrganizerExecutor remains the only application component allowed to call mutating Storage methods.

## API principals, RBAC, and security audit

The API transport resolves environment-owned bearer credentials into provider-neutral principals
at startup. Configuration roles normalize to explicit permissions before requests enter the route
dispatcher; authentication failure is 401 and authenticated insufficient authority is 403. Engines,
Storage adapters, Task execution, and strategy policies know nothing about API roles.

SQLite v9 adds append-only redacted API security audit records. A request receives a random request
ID and stores only principal ID when known, method, a normalized route template, action, outcome,
status, timestamp, and bounded source address. Headers, bodies, query strings, tokens, cookies,
exception text, and media payloads are never persisted. A pre-dispatch audit write occurs before a
mutation request can create a Job; persistence failure therefore fails closed. Audit reads are
available locally without Storage construction and remotely only to auditor/admin principals.

Remote organization remains the intersection of two independent capabilities: the principal must
have `remote_execute`, and Phase 18.5 must atomically consume a valid one-time authorization. RBAC
does not widen Scheduler commands or bypass conflict, overwrite/delete, Task authority, or
OrganizerExecutor safeguards.

## Operational dashboard read model

Phase 18.7 adds a provider-neutral immutable DashboardSnapshot assembled by a small application
query service. Runtime configuration supplies enabled ResourceLibrary/MediaLibrary counts; a
DashboardRepository supplies aggregate FileIndex, Task, AutomationJob, pending confirmation, and
notification dead-letter counts. The SQLite implementation uses grouped/count SQL and never loads
the large FileIndex into memory. If FileIndex has not been initialized, it reports an empty index
without creating that table.

Recent failures contain only kind, persistent identifier, categorical status/category, and time.
Raw Task/Job errors, media paths, notification bodies, headers, destinations, query strings, and
credentials do not enter the read model. `mediaflow dashboard` and authenticated
`GET /api/v1/dashboard` reuse this service. Dashboard reads construct no Storage adapter, perform no
health probe or network request, and remain covered by the normalized Phase 18.6 security audit.

## Conflict confirmation service boundary

Phase 18.8 exposes existing persistent confirmations through bounded list/show/audit API reads and
a least-privilege resolution route. Resolution delegates to ConfirmationService rather than
duplicating ConflictResolver behavior in the transport. SQLite atomically changes the confirmation,
appends its immutable decision audit, and transitions the related waiting TaskItem to skipped or
pending. A failed audit/item write rolls back the entire decision, and concurrent attempts can
commit only once.

Remote decisions are deliberately narrower than local operator capability: only Skip and Rename
are accepted, the actor is the authenticated principal, and arbitrary destination changes,
Manual, Overwrite, execute authority, and client-supplied audit identity are rejected. Resolving a
confirmation never constructs Storage, queues a Job, resumes a Task, or executes a plan. A later
explicit retry/resume re-enters the normal Planner/ConflictResolver/OrganizerExecutor boundaries.

## Persistent metadata review queue

Phase 18.9 adds immutable provider-neutral MetadataReview snapshots for production
NeedConfirm/Ambiguous outcomes. MetadataReviewService bounds candidates and score components,
persists them with the TaskItem transition to `waiting_metadata` in one SQLite transaction, then
the Task coordinator releases the source lock. A unique TaskItem constraint prevents duplicate
review records, and waiting metadata is excluded from blind failed-item retry.

The queue preserves RecognitionType (including C) and captures only identifiers, query context,
titles/years, matched-title evidence, and bounded scores. It deliberately excludes provider DTOs,
alternative-title collections, overview/images, HTTP/cache data, credentials, and raw exceptions.
CLI and authenticated API list/show paths are read-only repository operations. Phase 18.10 adds an
explicit rank-only resolution command and least-privilege API action. SQLite atomically changes the
review to resolved, appends immutable decision audit, and transitions its TaskItem from
`waiting_metadata` to `pending`; concurrent decisions commit once. Resolution constructs no
Storage/provider, creates no Job/Task, and never resumes automatically.

A later explicit `tasks resume` re-runs Parser, Recognition, and policy resolution. The saved
RecognitionType, MetadataPolicy, provider, and media type must still match; stale decisions fail
closed. Only then does the existing MetadataIdentificationService provider-ID details path obtain a
canonical MediaIdentity before unchanged Naming/Classification/Planner/Executor stages. The review
snapshot is never promoted directly into MediaIdentity, C remains C, and original execution
authority cannot be widened.

## Persistent classification review and configured-rule selection

Phase 18.11 captures only production `unclassified` outcomes. ClassificationReviewService takes
the resolved ClassificationPolicy and snapshots a bounded deterministic list of its enabled rules;
each choice contains a configured rule ID, MediaLibrary ID, and already-validated relative path.
SQLite v12 atomically creates review/choices with `waiting_classification`, or resolves one rank
with immutable audit and a waiting-to-pending TaskItem transition. Source locks are released while
waiting, and concurrent resolution commits once.

Neither queue creation nor resolution changes ClassificationEngine matching semantics. A decision
cannot invent a destination. On explicit Task resume, StrategyTestRunner verifies RecognitionType,
ClassificationPolicy, enabled rule, MediaLibrary ID, and relative path against current configuration,
then ClassificationPreviewService produces a manual configured-rule result. Stale configuration
fails closed. Resolution itself creates no Storage/provider/Task/Job and performs no planning or
execution; normal DryRun and execute authorization remain downstream.

## Classification policies and engine

Classification is the pure “where does this identified media belong?” stage after Naming. The
domain owns immutable `ClassificationPolicy`, `ClassificationRule`, `ClassificationContext`, and
`ClassificationResult` models. The application `ClassificationEngine` depends only on those
models; it has no Storage, filesystem, network, MetadataProvider, or OrganizerExecutor dependency.

A rule may constrain provider-normalized media type, genres, countries, languages, canonical year
range, and keywords. Conditions across fields are ANDed; configured alternatives within one field
are ORed. Keyword evidence is searched in normalized identity titles, provider alternative/
translated titles, overview/keywords, and parser title candidates. Classification uses the already
resolved MediaIdentity and never invokes metadata itself.

TMDB genre display names are localized by the details request language, so the TMDB adapter maps
known stable genre IDs to provider-neutral canonical genre names before constructing
`MediaIdentity`. Unknown IDs retain the provider name. Countries continue to use ISO 3166-1 codes.
This keeps development/user ClassificationPolicy rules independent of TMDB response language
without putting provider-specific IDs or translations in `ClassificationEngine`.

Enabled matching rules sort by descending priority and then stable rule ID, so output is
deterministic regardless of configuration tuple order. The selected rule returns a MediaLibrary
ID/display name plus safe relative category path. There is no default category or first-rule
fallback: no match produces `unclassified` with an empty library/path.

Development policy A has explicit Japanese-animation, animation, and action movie rules; policy B
has an explicit TV-series rule. RecognitionType C resolves ClassificationPolicy A but the
`ClassificationContext` and result retain RecognitionType C. `strategy-test --show-classification`
previews the rule, library, category, path, evidence, and warnings without executing Organizer or
mutating Storage.

## Organize planning and conflict detection

`OrganizePlanner` combines the configured MediaLibrary root, the safe Classification relative
path, and Naming directory segments/filename into a deterministic destination. Its public plan
operation is one of MOVE, COPY, LINK, NOOP, or SKIP; Phase 11 never emits an executable mutation
command list and never calls `OrganizerExecutor`. The configured MediaLibrary root is the only
input that may be absolute; it is normalized independently (including harmless trailing slash
removal) before relative Classification and Naming components are appended. Absolute or traversal
components from either downstream result remain invalid and can never replace the configured root
during `posixpath.join`.

The planner rejects absolute/traversal/NUL-bearing downstream components before a destination can
escape into a plan. A same-storage normalized source/destination becomes an explicit NOOP. Optional
read-only conflict inputs detect an existing destination through `Storage.exists`, another source
claiming the same target, and an already-known provider/provider-ID. These produce independent
DESTINATION_EXISTS, TARGET_COLLISION, and DUPLICATE_MEDIA records and remain unresolved; the
requested operation is preserved for a future confirmation/execution phase.

Phase 20.2 adds an optional read-only Hash evidence step after that destination is known and before
conflict resolution. `HashPolicy` is part of OrganizePolicy and defaults to `NONE`, which performs
no Storage `stat` or `read`. `FAST` calculates versioned `sha256-size-prefix-v1` evidence over the
reported size plus a configured bounded leading sample; it is probabilistic duplicate evidence,
not a full-content checksum. `FULL` calculates versioned `sha256-full-v1` while streaming the exact
reported object length in bounded chunks and rejecting premature EOF, excess data, cancellation,
Storage errors, files above the configured maximum, or changed size/type/modified time on the
mandatory post-read `stat`.

`HashDuplicateDetector` compares source and destination through provider-neutral Storage ports.
Different sizes are unique without content reads; matching size and mode-specific digest is a Hash
duplicate; incomplete evidence is indeterminate. `apply_hash_duplicate_detection` attaches the
evidence to the immutable plan, adds `DUPLICATE_MEDIA` or fail-closed `UNKNOWN`, and preserves the
requested operation and all existing conflicts. It never chooses a conflict strategy or calls a
mutation. Hashes are deliberately not persisted or calculated by Scanner/FileIndex in this phase.

`strategy-test --show-plan` composes the existing Parser, Recognition, Metadata, Naming, and
Classification services before calling the same planner. It displays the operation, source,
destination, conflicts, and `Execution: NOT EXECUTED`; it does not calculate conflict resolutions
or invoke Storage mutation methods.

## Organizer execution

`OrganizerExecutor` is the sole mutation boundary. Its default `execute=False` mode validates the
plan and returns an immutable DRY_RUN `ExecutionResult` without accessing Storage. Real execution
requires an explicit boolean from the CLI `--execute` boundary, validates source/destination and
unresolved conflicts before mutation, creates the destination parent through Storage, performs
MOVE/COPY/LINK through Storage methods, and verifies the destination afterward.

Same-adapter operations use native Storage move/copy/link capabilities. Cross-storage COPY streams
from `Storage.read` to `Storage.write`; cross-storage MOVE uses the same copy, verifies target
existence and size, and only then calls source `delete`. A failure before any completed mutation is FAILED; a failure
after directory creation or another completed step is PARTIAL. ExecutionResult records status,
operation, paths, created directories, completed operations, warnings/errors, timestamp, stable
plan ID, and duration. Structured Logger records contain the same non-secret execution context.

For Phase 12.2, OrganizePlan preserves the original source path exactly as supplied (absolute for
real local inputs) and carries a portable destination relative to the execution Storage root. The
destination combines the logical MediaLibrary root (for example `Movies`) with the strictly
relative Classification/Naming path. The physical execution root is never stored in OrganizePlan.
Immediately before execution, OrganizerExecutor independently verifies the logical root plus
relative suffix against the portable destination. A tampered target, absolute relative component,
or traversal is rejected before any Storage access.

Storage adapters still consume their own logical paths. The CLI therefore binds the preserved
absolute source to a configured ResourceLibrary-rooted LocalStorage and passes a separate logical
source path to Executor without rewriting the plan. Likewise it binds `--execution-root` as the
destination LocalStorage root while passing the portable plan destination to Storage. The
ExecutionResult retains the plan source/destination and separately exposes the fully resolved
destination for audit. Dry-run can resolve this full destination without accessing Storage.

The developer `strategy-test` CLI accepts real execution for one explicitly selected local file
only and requires an existing `--execution-root`/`MEDIAFLOW_EXECUTION_ROOT`; without `--execute`,
even `--show-plan` returns DRY_RUN. The production `mediaflow` CLI is a separate Phase 13 boundary:
it resolves configured Storage identities and supports ResourceLibrary batches through
`mediaflow organize --execute`, while defaulting to DryRun.

## Strategy recognition configuration bootstrap

Recognition configuration is separated into three sources. `smoke_strategy_configuration` owns
only test-fixture `/A/`, `/B/`, and `/C/` rules. `development_strategy_configuration` uses stable
ResourceLibrary IDs (`movies`, `tv`, `special`) rather than absolute paths. User/production-style
JSON is converted by `load_strategy_configuration` into the same immutable RecognitionType,
RecognitionRule, and RecognitionTypePolicy models consumed by `RecognitionRuleEngine` and the
policy resolver; there is no CLI-specific matching engine.

User JSON also binds configured scan roots to ResourceLibrary IDs. Directory bootstrap chooses the
most specific containing root, constructs the Scanner ResourceLibrary with that ID, and carries it
through each discovered FileContext into RecognitionContext. `--resource-library-id` is an explicit
one-off override, with `--resource-library` as its preferred alias. Single-file bootstrap uses the
same most-specific-root resolver before constructing FileContext, so directory and individual-file
tests receive identical ResourceLibrary evidence. Rules therefore remain portable when a library
moves between disks. A missing
match returns Unrecognized exactly as the engine normally does; there is no hidden default A.
Catch-all behavior requires an explicit `always` rule with visible priority.

The CLI reads user JSON only at its adapter boundary through `--config` or
`MEDIAFLOW_STRATEGY_CONFIG`. Invalid files fail before scanning. Downstream MetadataPolicy and
NamingPolicy catalogs retain the existing configured registries, and every user type-policy
reference is validated during runner bootstrap. C continues to resolve Metadata C and Naming/
Classification/Organize A without changing RecognitionType C.

Phase 22.4 adds a managed Web/API journey without introducing another recognition engine or
configuration authority. `recognitionTypes`, `recognitionRules`, and `recognitionTypePolicies` are
edited inside the existing optimistic whole-document Draft; edits are audited and return the
revision to Draft, while the shared runtime loader remains the canonical priority and reference
validator. The synthetic Strategy Test is accepted only for an exact Validated revision
ID/version/digest and enabled ResourceLibrary. It constructs no Storage or Provider: the configured
production `MediaParserService`, `RecognitionRuleEngine`, and `RecognitionTypePolicyResolver`
consume the supplied path directly.

The latest bounded, secret-free Strategy Test outcome is persisted beside the managed revision and
is projected with an explicit current/stale comparison. Matched, ambiguous, and unrecognized are
engine outcomes rather than hidden defaults; configuration/engine failures retain zero-side-effect,
retry-safe recovery evidence. Checked activation requires current passed Local setup evidence and
current completed Strategy Test evidence; Phase 22.6-F additionally requires current successful
destination-precheck evidence when the document declares a Local-backed MediaLibrary. Activation
still starts no scan or Preview, and resident API/Worker work continues to consume the immutable
Active snapshot through the existing snapshot binding and saved-revision resolver.

Independent review closed Phase 22.4 on 2026-08-26. The accepted Web projection renders bounded
matched rules, alternatives, reasons, and warnings. Its persisted `nextAction` is outcome-specific:
matched permits explicit review/activation, while ambiguous and unrecognized direct Draft
correction, validation, and explicit rerun. This closure does not add live Provider testing or
MetadataPolicy editing.

Phase 22.5-A was independently closed on 2026-08-26. `metadataPolicies` now use the same managed
Draft/API/Web object path, optimistic versioning, audit, direct-reference protection, canonical
runtime validation, and stale evidence semantics. A matched offline Strategy Test projects the
provider-neutral effective MetadataPolicy actually resolved from that exact revision; it constructs
no Provider or Storage and ambiguous/unrecognized outcomes do not fabricate policy content.

Phase 22.5-B, including its F1 correction, was independently closed on 2026-08-26. It adds an explicit live action on that same
exact-revision Strategy Test. Offline remains the default and constructs no Provider. Live Provider
bootstrap is shared by CLI/service, receives only the effective policy's Provider ID, and reads its
credential from the service environment. The production Parser → Recognition → TypePolicy →
MetadataProvider → CandidateMatcher path produces a bounded provider-neutral evidence projection:
at most five candidates and six score components per candidate, with normalized identity,
canonical/regional year and matched-title source. Provider exceptions and transport DTOs do not
cross the evidence boundary. This is a test journey only: it starts no scan, task, preview,
activation or storage mutation and does not change checked-activation semantics. Provider
switching and free-form manual correction continuation remain TARGET work.

Independent review on 2026-08-26 assigned three CURRENT defects to Phase 22.5-B-F1 and subsequently
closed that focused correction after re-review. The API now owns one thread-safe lazy
service-lifetime Provider registry/cache; immutable effective-policy timeout/retry controls are
supplied per TMDB request without mutating the shared client; and the provider-neutral evidence
projection applies deterministic UTF-8 byte-budget fitting with explicit total/projected/truncated
fields. Provider construction occurs only for an explicit live action, failed initialization is not
cached, and lower-ranked candidates are discarded before winning title/year evidence. This accepted
F1 boundary does not add Provider switching, manual Metadata correction or cache telemetry.

Phase 22.5-C and its F1/F2 durable concurrency corrections passed final Integration Acceptance on
2026-08-26. For the latest persisted, current live
`NeedConfirm`/`Ambiguous` evidence, the Web may submit only exact revision identity, exact evidence
time and one projected candidate rank. The Application resolves Provider ID/media type from that
repository evidence, revalidates the effective MetadataPolicy and RecognitionType through the
existing exact-revision Strategy runner, and uses the existing direct Provider-ID identification
path. A bounded provider-neutral selection explanation is saved with the new outcome. Stale,
offline, non-reviewable or unprojected selections fail before Provider access; this test-only path
constructs no Storage and starts no scan, Task, Preview, activation or downstream naming/planning.
Phase 22.5-D is accepted CURRENT implementation. One authenticated managed
action validates exact revision and evidence identity, derives RecognitionType/MetadataPolicy/
Provider from persisted evidence, and passes a bounded query/year/Movie-TV or direct-ID
`MetadataCorrectionSelection` through the existing live Strategy runner. Its bounded correction
context is stored in the existing evidence JSON and replacement uses the existing revision-plus-
evidence CAS. The Web uses the same action and existing candidate confirmation; no second store,
Storage construction, activation, scan, Task, Preview, or media execution is added. Provider
switching remains TARGET work. Phase 22.5-E is accepted CURRENT implementation after independent
High re-review of `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` on 2026-08-27, which also closed
Phase 22.5 at the phase level: queue exactly one resolved File correction as a new DryRun
continuation pinned to the source Task configuration, without generic Task resume, sibling replay, or
execute authority.

The shared API/Web admission service validates the exact File/review/source Task/TaskItem linkage,
correction version, active capacity, and immutable snapshot ID/digest, then atomically creates the
continuation and one-item non-executable Job. The claimed Worker fences those identities before
Provider or Storage construction, loads the pinned snapshot, and runs the existing read-only
Parser → Recognition → RecognitionTypePolicy → Metadata → Naming → Classification → Planner path
with the correction. It creates a new DryRun Task/Item/Result and requires the persisted Result before
completion. Query correction evidence includes one search plus one detail lookup; direct ID includes
detail only. RecognitionType C remains C. Files detail renders queued/running/completed/failed,
stale, and cancelled states with bounded recovery; source files, source review, source Task, and
sibling items are unchanged.

### Slice 22.6 managed policy configuration architecture (CURRENT; PASS / CLOSED)

The closed Slice adds NamingPolicy to the same managed whole-document
authority. `ConfigurationObjectService` normalizes the exact runtime-loader shape, validates every
template with the existing restricted renderer, reports RecognitionTypePolicy inbound references,
and delegates create/update/copy/delete to the existing revision CAS and audit transaction. It does
not introduce a second Naming model or configuration store.

Offline naming preview consumes one captured Draft/Validated revision and uses
`NamingPolicyRegistry -> NamingPreviewService -> NamingEngine -> SafeTemplateRenderer ->
NameSanitizer`. Synthetic samples are converted to the existing provider-neutral MediaIdentity and
ParseResult types; path mode invokes only `MediaParserService` and retains no full supplied path in
durable evidence. SQLite configuration-management schema marker 6 adds one revision-keyed bounded
preview-evidence table. Evidence always carries exact revision ID/version/digest and becomes stale
after an edit. Rendering and all failure paths construct no Storage/Provider/Task/Job/queue and grant
no execute authority. Classification, MediaLibrary resolution, conflict/capability checks, and
Organizer remain outside this service. This offline action does not by itself change checked
activation semantics.

ClassificationPolicy uses that same managed object authority. Normalization builds
the existing `ClassificationRule` and `ClassificationPolicy` domain types, so rule ordering and
relative-path safety remain owned by the production classification stack. RecognitionTypePolicy
inbound references block delete, while MediaLibrary existence remains a whole-Draft validation
concern rather than a new save-time rule.

Exact-revision classification preview converts one bounded sample to the existing
MediaIdentity/ParseResult/RecognitionType/ClassificationContext types and calls
`ClassificationPolicyRegistry -> ClassificationPreviewService -> ClassificationEngine`. Its
revision-keyed bounded evidence records classified/unclassified state, matched rule and evidence,
MediaLibrary resolution, relative path, warnings and recovery, and becomes stale after any edit.
The path constructs no Storage/Provider/Task/Job/queue and has no execute authority. OrganizePolicy,
composed destination paths and conflict/capability/existence prechecks remain outside this preview.
Managed normalization is semantically identical for runtime, so an edited policy loads into the
same domain `ClassificationRule` objects the loader produces from the original document.

OrganizePolicy uses that same managed object authority and provides an exact-revision offline
organize authority explanation. Normalization delegates to the runtime loader entry point
`parse_organize_policy`, so operation, conflict strategy, attachment, duplicate-detection, rollback
and source-directory-cleanup bounds — including the `overwrite`/`conflictStrategy` cross-field rule —
stay owned by the production `OrganizePolicy` domain object and cannot diverge from the Active
snapshot. The managed layer adds only unknown-field rejection, the bounded ID, and an editor
restriction to Move, Copy, HardLink and SoftLink that refuses `delete` and `create_directory` without
changing the loader. RecognitionTypePolicy inbound `organizePolicy` references block delete until
repointed.

The organize authority explanation resolves the requested RecognitionType through the production
`RecognitionTypePolicyResolver` against the exact Draft/Validated revision. Its revision-keyed
bounded evidence records RecognitionType, RecognitionTypePolicy, OrganizePolicy, operation, conflict
strategy, overwrite and delete authority, attachments, duplicate detection, rollback, source-directory
cleanup, the Storage capabilities the operation requires, an explicit statement that an unsupported
capability is a failure rather than a silent fallback, destructive-authority warnings, current/stale
state and recovery. Required capabilities are declared from the resolved policy, never probed: the
path constructs no Storage, Provider, Planner, Executor, Task, Job or queue, reports
`sideEffects: none` with `retrySafe: true`, and grants no execute authority. Every
`PolicyResolutionErrorCode` becomes an explained failure with a next action.

Destination-root normalization, relative-path/filename safety and composition are extracted
into dependency-free domain organizer helpers. `OrganizePlanner` delegates to those helpers, and the
exact-revision destination preview calls the same helpers after using the shared production policy
catalog plus the production Naming and Classification engines. It resolves only the selected
MediaLibrary's `rootPath` and `storageId` label from that revision; it never reads or applies the
Storage configuration root/mount prefix. Revision-keyed evidence attributes the RecognitionType,
type policy, naming policy, classification policy/rule and MediaLibrary contributions, with both
root-relative and composed Storage-relative results or a bounded unsafe/failure recovery. The path
constructs no Storage, Provider, Planner or Executor and preserves C identity.

The managed read-only destination precheck supports Local destination Storage
only. It reuses the Phase 22.6-D resolution and composition unchanged, then constructs the
destination Storage adapter from the unmodified revision document, reads its declared capabilities
before wrapping, and performs every probe through a `ReadOnlyStorageGuard` subclass whose
Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls raise. Inside that guard it reuses
the production `OrganizePlanner.plan` and `ConflictResolver.apply_configured` to report
destination-root existence and directory state, the deepest existing ancestor, the bounded directory
list that would have to be created, target existence, and the conflict outcome projected for the
configured strategy. Declared capabilities are compared against the capabilities required by the
resolved OrganizePolicy, and a missing capability is a `capability_gap` verdict with no fallback to
Copy or Move. Evidence is revision-keyed with exact version/digest CAS, and records
`pathScope: storage_relative` and `sideEffects: none` together with guard mutation counters that
must all be zero and a bounded read-operation list. It grants no overwrite, delete or execute
authority. Storage errors, capacity exhaustion and the overall deadline map to bounded categories
with explicit recovery. That evidence is part of checked activation for documents
that declare at least one MediaLibrary backed by Local Storage. The gate reads only the immutable
revision document and persisted evidence: missing, stale, failed and `capability_gap` evidence
refuse with bounded recovery, while remote-only or MediaLibrary-free documents report the
requirement as not applicable and retain the existing two gates. Unchecked activation is unchanged.
Both Web checked-activation controls use this same decision before they offer the
action: the shared Local applicability/current/completed/non-`capability_gap` predicate also feeds
the destination-precheck section, the guided control's bounded recovery line, and the
revision-detail compatibility warning. Both control sites name the destination requirement only once
the Local setup check and Recognition Strategy Test are current, so the sentence always names the
requirement the server refuses on first. A missing `mediaLibraries` document section is likewise not
applicable at the activation gate. The gate still reads only the revision document and persisted
evidence; it constructs no Storage, Provider, Planner or Executor and performs no probe.
The same precheck supports one to eight samples under one
RecognitionType. Each sample is validated and composed independently through the same production
path; all samples must resolve to one destination Storage, and the whole run keeps one capacity
lease, one `_ReadOnlyDestinationStorage` guard, one worker submission and one overall deadline.
`OrganizePlanner.plan` is called once per sample with `claimed_destinations` accumulating distinct
`destination-precheck-source-<index>.mkv` synthetic sources, so a production
`ConflictType.TARGET_COLLISION` between two composed destinations is detected with zero mutation;
the run then fails with the bounded `duplicate_destination` category, retaining every sample row
and a collision list naming the destination and the colliding sample indexes. Samples routed to
MediaLibraries on more than one destination Storage fail with `multiple_destination_storages`
before any probe, naming only Storage `id` and `type`. Completed evidence aggregates the
per-sample projected outcome by severity (`manual_confirmation_required`,
`overwrite_requires_confirmation`, `rename`, `skip`, `ready`, most severe first, or
`capability_gap` when any required capability is missing) and adds `sampleCount`, `items` and
`collisions`; the single-sample request and evidence keep their existing keys and add the same
three keys. `capability_gap` has run-level precedence; otherwise the most severe non-null projected
outcome wins, including `ready` when all rows are ready. Every `result.items[]` row has the same
ordered ten-key contract: `index`, `relativeDestination`, `destinationPath`, `targetExists`,
`plannerConflicts`, `projectedOutcome`, `proposedRelativeDestination`, `failureCategory`, `message`,
`nextAction`. The activation gate is byte-identical and refuses both new categories through its
existing failed branch.
Each `result.items[]` row carries its per-sample `failureCategory`, bounded `message` and, for a
failure, its own `nextAction`; that action comes from the same `_destination_sample_next_action`
map as the run-level action, while a row without one retains the bounded `-` fallback in the Web.
The read-only Web rows table renders all six columns — Sample, Destination, Projected outcome,
Failure category, Message and Next action — without deriving or changing them.
Remote SMB/OpenList/S3 destination prechecks, mutation-based capability probing,
multiple RecognitionTypes or destination Storages in one request, `ConflictType.DUPLICATE_MEDIA` /
known-media detection, attachment prechecks, absolute mounted-path display and execution remain
TARGET. Provider switching, generic Task resume and unattended execute also remain outside Slice
22.6. Per-item Processing Checkpoint recovery was subsequently delivered by Slice 23; it is not a
retroactive claim of the closed 22.6 boundary.

## Deferred work

Phase 15 persists organize conflicts as `waiting_confirm` records in SQLite. `ConflictResolver`
applies configured Skip/Rename decisions without mutation; Manual and Overwrite enter the durable
confirmation queue. Rename uses bounded `Storage.exists` probes and produces a replacement plan.
Overwrite requires an overwrite-enabled policy plus a fresh persisted high-risk confirmation.
Only OrganizerExecutor consumes the resulting authorized plan and remains the sole mutation
boundary. Decision audit records are append-only, and invalid destinations cannot be overridden.

Metadata and classification review/resolution APIs and bounded operator UI views exist. The broader
in-context decision → continuation → result/recovery Web journey remains incomplete, but the bounded
resolved File correction → single DryRun continuation path is implemented and accepted within the
closed Metadata configuration Slice.
Unresolved conflicts/reviews block execution, and silent delete remains unavailable.

## Minimal operator Web UI

Phase 19.1 adds a dependency-free same-origin adapter at `/ui/` to the existing WSGI API process.
Static HTML/CSS/JavaScript is returned before authentication or repository dispatch, so loading the
shell performs no persistence, Storage, Provider, Task, Job, or execution operation. Browser
security headers restrict scripts, styles, connections, framing, forms, referrers, and device
permissions to the smallest useful set; UI assets are never cached.

The page is not a second application service. It calls only the existing authenticated Dashboard,
confirmation, metadata-review, and classification-review endpoints. Untrusted values are rendered
as text nodes. A bearer token is held in one in-memory JavaScript variable, cleared from the input,
and never placed in a URL, DOM output, browser persistence, cookie, or application log. Existing API
RBAC, principal-derived actor identity, exact-field validation, atomic decision persistence, and
security audit remain authoritative.

The exposed write surface is intentionally narrower than the API: conflict Skip/Rename, persisted
metadata candidate rank, and persisted classification choice rank. The UI cannot resume a Task,
create/cancel a Job, request execute authority, Overwrite, or edit paths and identifiers. It does
not change any strategy engine or Organizer boundary.

## API credential lifecycle and transport guardrails

Phase 19.2 keeps bearer credentials environment-owned. Token generation uses the operating-system
cryptographic random source, prints once, and never loads configuration. Credential inspection
loads only JSON and reports Principal/role/environment names plus SET/UNSET; it never opens SQLite
or reveals a value, length, hash, or secret-derived identifier. Rotation uses overlapping,
separately named configured Principals and controlled process restarts, not secret persistence.

The development WSGI listener remains loopback-only by default. Deterministic validation accepts
localhost plus IPv4/IPv6 loopback; any other valid bind needs
`--allow-insecure-remote-http` and emits a warning. The acknowledgement supplies no TLS. A trusted
external reverse proxy remains responsible for HTTPS, certificates, and network policy.

JSON responses use no-store, nosniff, no-referrer, and frame-denial headers; 401 includes a Bearer
challenge. Authorization parsing accepts one bounded, non-whitespace Bearer credential and still
compares against every configured Principal using constant-time comparison. RBAC and the separate
one-time remote-execution authorization remain unchanged.

## Read-only Task and Job observability

Phase 19.3 extends the same operator UI and authenticated API with bounded Task, Job, TaskItem, and
ResultRecord visibility. Collection queries accept a 1–100 limit. Task detail independently bounds
items and results; SQLite fetches only limit+1 rows so the transport can report truncation without
enumerating a large batch. Stable repository ordering remains authoritative.

The UI renders status, counters, authority mode, stages, linked Task IDs, and destination outcomes
using text nodes. It issues no Task/Job POST and exposes no resume, retry, cancel, submission,
authorization, or execution control. Reads do not construct Storage or MetadataProvider adapters;
the only write remains the existing normalized security-audit record for an authenticated request.

## Stable operational-history cursors

Phase 19.4 replaced the Phase 19.3 first-page-only limitation with forward keyset pagination;
Phase 19.5 adds bounded reverse keyset queries and Previous navigation.
Tasks/Jobs use newest-first `(created_at, ID)` ordering; TaskItems/Results retain oldest-first
processing order. SQLite applies the composite boundary before `LIMIT`, never OFFSET or prior-row
enumeration. The established cursor boundary therefore remains stable when newer records arrive.

The opaque URL-safe v2 cursor has a strict next/previous direction, version, resource kind,
timezone-aware ordering timestamp, and
stable record ID. Decoding strictly bounds length and validates Base64, JSON schema, version, kind,
timestamp, and ID. It contains no media or secret fields and query strings remain excluded from
security audit. Valid v1 cursors decode as next cursors for compatibility, while only v2 is emitted.
Reverse queries invert SQL ordering around the boundary, take `limit + 1`, then restore canonical
order; they never enumerate prior rows or use OFFSET. TaskItem and Result cursors advance
independently. The UI exposes explicit Previous/Next and first-page refresh; arbitrary jumps, totals,
and live polling remain deferred.

## Read-only Scheduler and Notification operations

Phase 19.6 extends the same UI adapter without adding an application-service duplicate. Schedule
definitions remain configuration-owned and are joined with persisted `ScheduleState`; occurrence
audit reads keep SQLite's newest-first order and apply a caller limit of 1–100. Notification reads
apply the existing status enum and limit directly in SQLite. Unknown, duplicate, blank, and injected
query fields fail before repository access.

Only provider-neutral operational fields cross the API: IDs, types/statuses, attempts, safe
timestamps, categorical failure reason, and numeric HTTP status. Webhook URL, payload/body,
signature, headers, response body, exception text, media paths, and credentials remain outside the
transport. The UI uses text nodes, explicit refresh, and no polling. These routes construct no
Storage, Provider, workflow service, Scheduler tick, delivery worker, or OrganizerExecutor; the only
persistent side effect is the existing normalized authenticated security audit.

Phase 19.7 extends the v2 directional cursor boundary to both histories. NotificationDelivery uses
newest-first `(created_at, delivery_id)` and ScheduleAudit uses newest-first `(emitted_at, audit_id)`.
Forward/reverse SQLite predicates apply before `limit + 1`; reverse results are restored to canonical
display order without OFFSET, totals, or prior-row enumeration. An opaque SHA-256 scope binds each
notification cursor to its status filter (`all` included) and each audit cursor to its schedule ID.
The scope reveals neither the configured identifier nor media/secret data and prevents cross-scope use.

## Persistent redacted operational logs

Phase 19.8 implements the existing `Logger` port with a SQLite adapter and a distinct immutable
`OperationalLogRecord`. SQLite v13 stores only UTC time, level, component, fixed event code, optional
validated Task/Job/Plan ID, and categorical status. The adapter maps a closed set of application
messages and discards all unrecognized messages and non-whitelisted context; paths, titles, raw
errors, provider/HTTP values, arbitrary JSON, and credentials have no persistence columns.

Logging is disabled by default and minimum level is configuration-owned. Scanner,
MediaOrganizerService, and OrganizerExecutor receive the same adapter without acquiring logging
policy. Local bounded listing opens no Storage/provider/workflow. Explicit prune applies age and
maximum-row retention only to `operational_logs`; it cannot delete media or other runtime records.
Web/API visibility, live tail, full-text search, and remote shipping remain deferred.

Phase 19.9 adds read-only API/UI visibility without expanding that schema. SQLite applies scoped
forward/reverse `(occurred_at, log_id)` keysets before `limit + 1`; reverse pages restore newest-first
order. The opaque scope binds `all` or the chosen minimum level. API output uses an explicit field
allowlist, existing READ RBAC, and normalized audit without queries. The UI uses text nodes,
in-memory credentials, explicit refresh, and no prune/write/live controls.

## Runtime database backup boundary

Phase 19.10 adds a local infrastructure-only `SQLiteBackupService`. The configured runtime database
is opened read-only and SQLite's online backup API writes a private temporary database in the target
directory. Integrity and runtime schema are checked before an atomic hard-link publication; an
existing destination wins the race and is never overwritten. Only the owned temporary file is removed
after failure. Verification opens candidates read-only, computes size/SHA-256, and cannot migrate them.

These commands construct no Storage/provider/workflow/API/Executor and do not alter source state.
Restore is deliberately absent because selecting and replacing an active production database requires
a separately designed shutdown, rollback, compatibility, and authorization procedure.

## Release validation boundary

Phase 19.11 adds no runtime service. A least-privilege GitHub Actions matrix repeats the offline
quality gate for each explicitly supported Python version, followed by a separate wheel job. The
wheel is inspected before installation and exercised from a temporary working directory and fresh
virtual environment, preventing an editable checkout from masking missing package files.

The artifact smoke path validates the console entry point, both canonical configurations, and the
SQLite backup boundary using only temporary local state. Live TMDB/SMB/OpenList/S3/R2 access,
credentials, media Storage, publishing, deployment, restore, and signing remain outside CI.

## Upgrade preflight boundary

Phase 19.12 adds a local read-only compatibility service. It reuses `SQLiteBackupService.verify` for
both the configured runtime database and an explicit operator backup, so integrity, schema-marker,
and newer-version behavior have one implementation. It compares schemas and reports whether the next
normal repository open would require migration without constructing `SQLiteTaskRepository`.

Backup freshness is an explicit bounded operational check over filesystem UTC modification time; it
is not identity evidence. The service also validates the declared Python support range and reports
installed package/schema versions. It never constructs Storage/provider/workflow/API/Executor,
migrates, creates a backup, replaces a database, detects service shutdown, or performs restore.

## Offline database restore boundary

Phase 19.13 permits recovery only when the configured runtime database and all SQLite sidecars are
absent. `SQLiteRestoreService` verifies the explicit backup, copies it through SQLite into an
owner-only same-directory temporary file, verifies/fsyncs the stage, and publishes via an atomic
no-overwrite hard link. It reports older supported schemas without opening the migration-capable
repository.

The service removes only its own stage after failure. It never moves, deletes, renames, or overwrites
an existing runtime/sidecar/backup and constructs no media Storage or workflow. Operators must stop
all MediaFlow processes and manually preserve the old database; empty-path checks are not a process
liveness guarantee.

## Isolated migration rehearsal boundary

Phase 19.15 copies an explicit verified backup through SQLite into an owner-only temporary database,
records representative core-table counts, and opens only that copy using the production
`SQLiteTaskRepository` migration path. It then verifies current Schema/integrity and unchanged counts
before deleting the copy and its rehearsal-owned sidecars.

The configured Runtime is used only to derive the existing shared process lease and is never opened.
Backup and Runtime remain unchanged on success and injected copy/migration failures. Rehearsal tests
the current artifact's forward migration mechanics; it does not perform production migration,
replacement, rollback, restore, service orchestration, or media Storage access.

## Cooperative runtime maintenance lease

Phase 19.14 wraps production CLI runtime operations with a process-lifetime advisory lease derived
from `persistence.databasePath`. Normal database/workflow/service commands take a non-blocking shared
POSIX `flock`; confirmed restore takes a non-blocking exclusive lease before invoking the restore
service. `finally` releases descriptors, and the kernel releases them after crashes.

The stable owner-only lock file is deliberately empty and retained after release so no unlink/recreate
inode race can split lock participants. Config validation, token generation, credential status, and
Storage preflight remain lock-free. Symlink/non-regular lock paths fail closed. This coordinates only
production CLI participants on POSIX; it is neither a distributed lock nor detection of unrelated or
direct-library processes, and exclusive restore is rejected where the mechanism is unsupported.

## Runtime strategy catalogs

The Phase 13 runtime boundary loads all strategy content from one JSON document selected by
`MEDIAFLOW_CONFIG`. It normalizes RecognitionRules, RecognitionTypePolicies, MetadataPolicies,
NamingPolicies, ClassificationPolicies, and OrganizePolicies into the existing immutable domain
models. Engines remain unaware of JSON and contain no A/B/C policy-ID branches.

Startup validates the complete reference graph: RecognitionRule to RecognitionType;
RecognitionTypePolicy to the four downstream catalogs; ClassificationRule to MediaLibrary; and
ResourceLibrary/MediaLibrary to Storage. Naming templates and classification relative paths are
validated by their existing safety rules. `mediaflow config validate` performs this same loading
and validation path without constructing Storage adapters or contacting metadata providers.

The canonical runtime content is `config/strategy.example.json`. Python smoke/development
constructors are isolated compatibility test fixtures, not production fallback configuration.
RecognitionType C remains the identity while resolving Metadata C and configured Naming,
Classification, and Organize A.

## Bounded Organizer compensation

Phase 20.3 keeps compensation inside `OrganizerExecutor`, the only mutation boundary. An opt-in
`RollbackPolicy` journals each successfully observed target and new directory for one invocation.
On later failure it compensates in strict reverse order and revalidates ownership before mutation.
COPY/LINK targets are deleted; same-Storage MOVE targets are moved back; cross-Storage MOVE restores
a deleted source through Storage read/write verification before target deletion.

The original execution remains failed even when compensation succeeds. Reappeared sources,
changed/unverifiable targets, and non-empty directories fail closed as partial rollback. This is not
historical rollback or a distributed transaction and cannot be combined with overwrite authorization.

## Read-only runtime configuration snapshot

Phase 19.16 adds a one-way projection from normalized `RuntimeConfiguration` into an immutable,
allowlisted `ConfigurationSnapshot` during API bootstrap. This projection constructs no Storage,
provider, Scanner, workflow, Scheduler/Notification worker, Planner, Executor, backup, restore, or
migration service. Requests only copy the already-frozen snapshot into JSON and never reload the
configuration or query runtime repositories; the existing security-audit append remains unchanged.

The projection deliberately reports only bounded, deterministically ordered catalog IDs, types,
states, counts, and RecognitionTypePolicy reference IDs. Paths, condition operands, templates,
classification destinations, endpoints, environment-variable identifiers/values, webhook fields,
credentials, and arbitrary adapter options have no output mapping. This makes omission structural
rather than dependent on pattern-based redaction. The authenticated System UI renders values only
through DOM text nodes and exposes refresh but no configuration or workflow controls.

## Durable metadata query correction

Phase 21.1 adds a separate durable `MetadataCorrectionReview` only for tracked Metadata
`NOT_FOUND`. It snapshots RecognitionType, MetadataPolicy/provider, query/year/media type and moves
the TaskItem to `WAITING_METADATA_CORRECTION`, releasing its source lock. Resolution records a
bounded corrected query/year/Movie-TV choice or direct configured-provider ID, audits the intent,
and returns the item to `PENDING`. Explicit Task resume injects that selection into the existing
MetadataIdentificationService: text corrections use real provider search/matching; direct IDs use
`identify_by_provider_id`. The effective Movie/TV policy is changed only for this identification
attempt. RecognitionType and all resolved downstream policy references remain immutable, including
C -> Metadata C / Naming A / Classification A / Organize A. SQLite schema v19 owns this correction
and audit state; correction commands construct neither Storage nor provider clients.

## Durable manual ignore decision

Phase 21.2 adds a narrow terminal operator outcome for TaskItems in WAITING_RECOGNITION,
WAITING_METADATA or WAITING_METADATA_CORRECTION. `ManualIgnoreService` resolves the item to IGNORED
only when the corresponding review is still pending. SQLite schema v20 atomically updates both rows
and appends a bounded immutable audit containing kind, review ID, actor and note. A concurrent or
stale resolver loses the conditional update and the transaction rolls back.

IGNORED is neither success nor failure: it is excluded from resume/retry, excluded from completed
item counts and forces a PartialSuccess Task summary. This database-only decision does not mutate or
hide the source, edit FileIndex/configuration, create a persistent path rule, invoke a provider, or
construct Storage/Planner/OrganizerExecutor. Batch ignore is implemented in Phase 21.5; API/UI
writes and classification/conflict ignore remain outside this phase.

## Durable Recognition re-evaluation request

Phase 21.3 adds a database-only `RecognitionRetryService`. For one pending RecognitionReview whose
TaskItem is still WAITING_RECOGNITION, SQLite schema v21 atomically records a bounded immutable retry
audit, marks the review `retry_requested`, and returns the item to PENDING. Conditional review/item
updates and the audit insert share one transaction, so stale, concurrent and injected failures roll
back completely.

The existing Task resume selector includes the pending item but supplies no RecognitionSelection.
The continuation therefore reruns the normal Parser and RecognitionRuleEngine using current
externally loaded rules and the original ResourceLibrary context. A current match proceeds normally;
an unchanged miss creates a new review under the continuation Task. The request command constructs
no Storage/provider/workflow, edits no rule/configuration, has no hidden A fallback, and cannot grant
execute authority. A current C match remains C while resolving configured downstream policy reuse.

## Bounded batch Recognition re-evaluation request

Phase 21.4 reuses the same immutable `RecognitionRetryDecision` audit and `retry_requested` review
status, and adds `RecognitionBatchRetryService` plus a repository transaction that processes a
bounded, oldest-first selection of pending reviews. Each selected review must still be pending and
its TaskItem must still be WAITING_RECOGNITION; one conditional update, item update, and audit insert
is executed per request inside the same database transaction, so a stale/concurrent member or an
injected audit failure rolls back the complete batch.

The CLI command is
`mediaflow recognition-reviews retry-pending --actor ACTOR [--note NOTE] [--limit N]
[--task-id TASK_ID]`. `--limit` is bounded to 1–100 and `--task-id` optionally scopes selection to a
single Task. The command constructs no Storage/provider/workflow, performs no media mutation, and
cannot grant execute authority. Resume semantics are identical to Phase 21.3: retried items are
selected without a `RecognitionSelection`, current rules are evaluated normally, and C preserves
Metadata C plus downstream A policy reuse.

## Bounded batch manual ignore

Phase 21.5 reuses the immutable `ManualIgnoreDecision` audit and `ManualReviewKind`, and extends
`ManualIgnoreService` with `ignore_pending`. A repository union query selects a bounded, oldest-first
set of TaskItems in WAITING_RECOGNITION, WAITING_METADATA or WAITING_METADATA_CORRECTION whose
matching review is still pending. Each selected review/item transition plus audit insert runs inside
one database transaction, so a stale/concurrent member or injected audit failure rolls back the
complete batch.

The CLI command is
`mediaflow tasks ignore-pending --actor ACTOR [--note NOTE] [--limit N] [--task-id TASK_ID]`.
`--limit` is bounded to 1–100 and `--task-id` optionally scopes selection to one Task. The command
constructs no Storage/provider/workflow, performs no media mutation, and cannot grant execute
authority. Ignored items remain terminal, excluded from resume/retry and completed counts, and
preserve the Phase 21.2 PartialSuccess Task summary semantics.

## Bounded batch manual RecognitionType decision

Phase 21.6 reuses the existing RecognitionReview snapshot/decision-audit models and extends
`RecognitionReviewService` with `resolve_pending`. A bounded, oldest-first selection of pending
reviews is resolved with one currently enabled configured RecognitionType. Every selected review
must contain that type in its stored snapshot and its TaskItem must still be WAITING_RECOGNITION;
review/item updates and audit inserts share one transaction, so a disabled/unknown type, missing
snapshot member, stale/concurrent member, or injected audit failure rolls back the complete batch.

The CLI command is
`mediaflow recognition-reviews resolve-pending --recognition-type TYPE --actor ACTOR [--note NOTE]
[--limit N] [--task-id TASK_ID]`. It constructs no Storage/provider/workflow, performs no media
mutation, and cannot grant execute authority. Resolved items return to PENDING and explicit resume
loads the durable RecognitionSelection; RecognitionRuleEngine and configuration remain unchanged,
and C preserves Metadata C plus downstream A policy reuse.

## Bounded batch Metadata query correction

Phase 21.7 reuses the existing MetadataCorrectionReview and decision-audit models and extends
`MetadataCorrectionService` with `resolve_pending`. A bounded, oldest-first selection of pending
Metadata NOT_FOUND corrections is resolved with one validated corrected query/year/movie-TV choice
or direct configured-provider ID. Each selected review must still be pending, its current policy/
provider must still be enabled and lookup-capable, and its TaskItem must still be
WAITING_METADATA_CORRECTION; review/item updates and audit inserts share one transaction, so a
disabled/stale policy or provider, invalid input, stale/concurrent member, or injected audit failure
rolls back the complete batch.

The CLI command is
`mediaflow metadata-corrections resolve-pending --media-type movie|tv [--query QUERY |
--provider-id PROVIDER_ID] [--year YEAR] --actor ACTOR [--note NOTE] [--limit N]
[--task-id TASK_ID]`. It constructs no Storage/provider/workflow, performs no media mutation, and
cannot grant execute authority. Explicit resume loads the durable MetadataCorrectionSelection and
reruns the existing provider path; RecognitionType C remains C while reusing downstream A policy.

## Bounded batch Metadata candidate selection

Phase 21.8 reuses the existing MetadataReview/candidate/decision-audit models and extends
`MetadataReviewService` with `resolve_pending`. A bounded, oldest-first selection of pending
NeedConfirm/Ambiguous reviews is resolved with one persisted candidate rank. Every selected review
must contain that rank and its TaskItem must still be WAITING_METADATA; review/item updates and audit
inserts share one transaction, so an invalid/absent rank, stale/concurrent member, or injected audit
failure rolls back the complete batch.

The CLI command is
`mediaflow metadata-reviews resolve-pending --candidate-rank RANK --actor ACTOR [--note NOTE]
[--limit N] [--task-id TASK_ID]`. It constructs no Storage/provider/workflow, performs no media
mutation, and cannot grant execute authority. Explicit resume loads the durable MetadataSelection;
RecognitionType C remains C while reusing downstream A policy.

## Bounded read-only file catalog CLI

Phase 21.9 adds `FileCatalogService`, a pure FileIndex query service. It accepts configured
ResourceLibrary and Storage IDs, reads records only through existing `list_by_resource_library`
ports, applies ResourceLibrary/Storage/scan-status and path/filename substring filters, and returns
a stable bounded result ordered by updated time and file ID. It never constructs Storage, Scanner,
provider, Planner or OrganizerExecutor and never reads file contents.

The CLI commands are `mediaflow files list [--resource-library ID] [--storage ID]
[--scan-status STATUS] [--query TEXT] [--limit N]` and `mediaflow files show FILE_ID
[--resource-library ID]`. Output is limited to indexed FileIndex fields; URLs, credentials, provider
payloads and raw errors are structurally excluded.

Phase 21.10 adds stable keyset cursors to `files list` with `--after/--before` plus
`--cursor-file-id`. Cursor filtering uses the same `(updated_at DESC, file_id DESC)` order as the
base catalog, after all existing filters, and remains bounded without OFFSET.

Phase 21.11 extends `files show` with the latest persisted Task result for the matching source
Storage/path. The detail view keeps the FileIndex record authoritative and renders the latest
result only when it exists; missing history is explicit rather than synthesized. The command still
constructs no Storage/provider/workflow and never reads file contents.

Phase 21.12 adds derived filters to `files list` for RecognitionType, Provider, Provider ID, Title,
Task ID, and Year. Existing FileIndex filters run first, then latest-result matching, then cursor
filtering and truncation. Records without a matching latest result are excluded when derived
filters are present, and derived filters fail closed without a Task repository.

Phase 21.13 pushes the base FileIndex query into a parameterized `FileIndexRepository.list_catalog`
method, implemented by both SQLite and in-memory repositories. `FileCatalogService.list` now
delegates ResourceLibrary/Storage/scan-status/query/cursor/limit filtering to the repository and
applies only latest-Task-result derived filters in memory.

Phase 21.14 pushes those latest-Task-result derived filters into a SQLite joined query. The
repository pairs each FileIndex row with its latest TaskResult for the same source Storage/path and
applies RecognitionType/Provider/Provider ID/Title/Task ID/Year predicates in SQL before cursor and
limit. The previous fallback remains for non-SQLite or unsupported repositories.

## Bounded batch failed-item retry request

Phase 21.15 adds SQLite schema v22 `task_retry_audit` and `TaskRetryRequestService`. A bounded,
oldest-first set of FAILED/PARTIAL TaskItems can be atomically returned to PENDING with stage
`task_retry_requested` and one immutable actor/note audit per item. The command is database-only:
it constructs no Storage/provider/workflow and cannot grant execute authority. Actual retry still
uses the existing explicit `mediaflow tasks resume ORIGINAL_TASK_ID` boundary.

## Bounded read-only file catalog status counts

Phase 21.16 adds `FileCatalogService.stats` and `mediaflow files stats`. It aggregates existing
FileIndex records by scan status after optional ResourceLibrary/Storage scoping, using only the
existing FileIndex repository read path. The command constructs no Storage/provider/workflow.

## Read-only file catalog Web UI

Phase 21.17 exposes the FileCatalogService through authenticated GET endpoints:
`/api/v1/files`, `/api/v1/files/{file_id}`, and `/api/v1/files/stats`. The existing operator UI
gains a Files view that renders bounded file lists and file detail, including the latest persisted
Task result when present. No UI form submits write/execute endpoints or constructs
Storage/provider/workflow adapters.

Phase 21.18 adds a read-only search/filter form to the Files view. It builds query parameters for
the existing `/api/v1/files` endpoint from only populated controls, including FileIndex and derived
latest-Task-result filters. The API continues to require READ permission and reject duplicate or
unknown query fields.

## Explicit batch DryRun/organize commands

Phase 21.19 adds `mediaflow batch preview` and `mediaflow batch organize` as explicit entry points
to the existing no-path all-ResourceLibrary pipeline. They do not introduce new workflow logic;
`batch organize` remains DryRun without `--execute` and preserves original-plus-fresh execute
authorization boundaries.

## File detail related Task/Review linkage

Phase 21.20 adds a bounded source-matched review link query for RecognitionReview,
MetadataReview, and MetadataCorrectionReview records. FileCatalogDetail and the Files API/UI expose
the latest Task result plus related review kind/review/status/task, allowing navigation without any
review mutation or provider lookup.

Phase 21.21 adds `mediaflow files re-recognize FILE_ID --actor ACTOR [--note NOTE]`. It resolves the
file's pending RecognitionReview and delegates to the existing RecognitionRetryService; actual
re-evaluation remains an explicit Task resume.

Phase 21.22 adds `mediaflow files re-match` for pending MetadataCorrectionReview. It delegates to
the existing MetadataCorrectionService with bounded validated query/year/media-type/provider-ID
inputs; actual Provider lookup remains a separate Task resume.

Phase 21.23 adds `mediaflow files re-plan FILE_ID --actor ACTOR [--note NOTE]`. It uses the file's
latest persisted TaskResult, requests retry for that specific FAILED/PARTIAL TaskItem through the
existing task retry audit, and leaves actual re-planning/organization to explicit Task resume.

Phase 21.24 adds a focused closure smoke test and documentation reconciliation. It verifies the
top-level CLI command families and read-only Files UI boundaries without introducing any new
production feature.

Phase 21.25 adds authenticated file-action POST endpoints for re-recognize and re-plan. The Files UI
renders these actions only when a pending RecognitionReview exists or the latest result is
FAILED/PARTIAL; actual work remains explicit Task resume.

Phase 21.26 completes the Phase 21 bounded file-detail actions with `POST /api/v1/files/{file_id}/
re-match` and a read-only Files UI form for pending MetadataCorrectionReview. The accepted Phase 21
manual workflow scope is now closed; Phase 22 configuration management is the next boundary.

## Bounded File/Media detail evidence and cross-links (Slice 24 Task 24.1)

Task 24.1 adds Runtime schema marker `27` with a forward-migrated `pipeline_evidence` table.
`MediaOrganizerService` captures a bounded, provider-neutral evidence document at each tracked
TaskItem boundary for waiting, DryRun, skipped, failed, partial and successful items. The document
contains normalized Parse, Recognition, Metadata, policy ownership, Naming, Classification, plan,
operation/effect and declared Storage capability sections; it structurally excludes raw Provider
DTOs, credentials, headers, cookies, private configuration and unbounded exception text. Records
created before evidence capture remain readable with section-level `unavailable` rather than being
reconstructed from status or filename.

`FileCatalogService.detail` now projects the authoritative FileIndex record together with bounded
captured evidence, related TaskItems and their Processing Checkpoints, related reviews/conflicts,
prior Results/effects and current checkpoint-derived actions. `GET /api/v1/files/{file_id}` remains
the shared detail surface, with additive sections, and `GET /api/v1/files/by-source` resolves an
existing TaskItem/review/conflict/Result source link to one current indexed File when unique. The
Operator Web renders evidence/history sections and offers inbound File/Media navigation from
TaskItems, reviews, conflicts and Result rows; missing, stale or ambiguous links produce an explicit
unavailable explanation instead of guessing a File ID.

## Configuration architecture: CURRENT

Through Phase 22.2/22.2R, JSON remains the compatibility bootstrap until an operator explicitly activates
the first managed revision. SQLite now also persists canonical managed Draft/Validated/Active
revisions, validation evidence, immutable digest/version identity, and redacted lifecycle audits.
Before activation the authority is explicitly `JSON_BOOTSTRAP`; a Phase 22.1 Storage CRUD row is not
Active. Credentials remain environment- or approved Secret Store-owned.

### Phase 22.1 Storage configuration CRUD foundation

Phase 22.1 adds the first durable CRUD slice. `ManagedStorageConfiguration` is separate from the
runtime loader's `StorageDefinition`; validation covers Local, SMB, OpenList, AWS S3, Cloudflare R2,
and generic S3-compatible shapes without constructing an adapter or contacting a service. It accepts
only environment-variable names for credentials and rejects literal or nested secret-like fields.

`StorageConfigurationService` provides create/read/list/update/copy/enable/disable/delete with
optimistic versions and Before/After audits. `SQLiteConfigurationRepository` persists generic
configuration-object, reference, and redacted audit records under a separate
`configuration_management` schema marker. Storage deletion and reference counting run in one SQLite
write transaction. A Resource/Media Library reference therefore blocks deletion by default.

The Storage object CRUD remains a separate foundation and is deliberately not treated as the source
of workflow truth. It is not itself the object-by-object configuration editor.

### Phase 22.2 / 22.2R Active Configuration Snapshot vertical slice

`ManagedConfigurationService` imports a canonical JSON document as Draft, validates it with the
existing normalized runtime loader without constructing Storage or Providers, and atomically
publishes one Active revision through `SQLiteConfigurationRepository`. The authenticated
`/api/v1/configuration` routes and the embedded Configuration view expose authority, lifecycle,
digest, bounded validation errors, redacted revision detail, diff sections, and explicit actions.
The local CLI additionally supports `config status`, `config draft-import`, `config draft-validate`,
and `config activate` for migration/debugging.

Runtime resolution reads the managed revision identity at process/work boundary. A missing or corrupt
managed revision fails closed; it does not silently fall back to JSON. New PersistentTask and
AutomationJob rows carry `configuration_snapshot_id` and `configuration_snapshot_digest`, and queued
Jobs resolve their pinned revision when executed. Activation itself creates no Storage adapter,
Provider request, scan, plan, or mutation. Full object CRUD and connectivity-test journeys remain
future vertical slices.

The 22.2R implementation makes the published revision sequence (`revisionSequence`) distinct from the
optimistic Draft edit token (`version`). SQLite maintains an explicit last-known Active authority
pointer, and the shared runtime validator checks the immutable bootstrap database locator before
validation and again immediately before activation. Import, validation, edit, and activation persist
their lifecycle state and bounded redacted audit evidence in one transaction. Configuration status and
whole-document recovery use the bootstrap locator when Active is unavailable. The Phase 22.2R-F1
repair validates the complete runtime before publishing an identity, keeps repeated requests
fail-closed, returns structured optimistic conflicts, resolves Scheduler definitions and identity from
one revision, and lets a Worker load a queued Job's saved revision from the immutable locator. The
production-entry-point Web → Worker → Task/Result pin regression is present. F2 replaces the
resident API's identity-only refresh with a request-captured immutable binding containing the revision
ID/digest, queue and protected-execute admission, execution-authorization TTL, stale-job threshold,
schedules, system status, MetadataPolicy references, and Dashboard counts. Candidate bindings are
fully normalized before one pointer is published, and refreshes are serialized so concurrent requests
observe a complete old or new binding. Saved Job revision failures cross the Worker boundary as
bounded trusted evidence and are persisted for API/Web recovery display. Legacy unpinned work is
rejected after managed authority exists. F2 passed independent review on 2026-08-24.
The outer Worker command itself reads only the immutable database locator and management bootstrap
boundary before claiming; it does not construct Storage or Providers until the claimed Job's saved
snapshot is selected.

The snapshot identity columns were additive compatibility migrations on Runtime schema 22. Slice 23
advances the Runtime marker additively through 23–26 for effect-certainty evidence, exact-version
recovery requests, recovery continuations and the bounded recovery-batch parent/child read model.
Slice 24 Task 24.1 advances it to `27` for the bounded pipeline-evidence File/Media detail read model.
Fresh and older databases receive the structures through forward migration, and Job inserts use an
explicit column list so historical ALTER-table column order cannot corrupt authority fields. Phase
22.3 closed on configuration-management schema marker `4`; Phase 22.4 adds marker `5` for
revision-bound Recognition Strategy Test evidence, Phase 22.6-A adds marker `6` for exact-revision
Naming preview evidence, Phase 22.6-B adds marker `7` for exact-revision Classification preview
evidence, Phase 22.6-C adds marker `8` for exact-revision organize authority evidence, Phase 22.6-D
adds marker `9` for composed destination-preview evidence, and Phase 22.6-E adds marker `10` for
read-only destination-precheck evidence. The configuration-management marker remains `10`; the
current Runtime schema marker is `27`.

### Phase 22.3 Local Storage + Library guided slice (CURRENT implementation; PASS / CLOSED)

`ConfigurationObjectService` is a narrow application adapter over the same managed whole-document
Draft. It edits only `storages`, `resourceLibraries`, and `mediaLibraries`, preserving all other
policy/catalog sections through canonical normalization. Local guided Storage accepts `id`, `name`,
`type=local`, host-absolute `rootPath`, and `readOnly`; ResourceLibrary and MediaLibrary accept only
runtime-consumed fields and enforce Storage-relative paths. Existing remote Storage values are
recursively redacted and read-only. Direct inbound references are calculated for Storage <-
Resource/Media, Media <- Classification result, and Resource <- explicit Recognition condition; delete
is rejected atomically while references remain.

The Local setup check is an explicit API/Web action bound to the exact Draft revision ID, edit version,
and digest. It clones selected Local Storage entries to read-only, constructs adapters through the
existing `RuntimeConfiguration.create_storages` factory, and performs only `Exists`/`Stat` against
one enabled ResourceLibrary and MediaLibrary root. Phase 22.3R3 places loader selection, Storage
construction, and all four probes inside one per-service capacity slot and one overall deadline.
Selected adapters are wrapped by the shared fail-fast read-only guard. Timeout does not claim to
cancel a running Python/OS call: the slot remains occupied until that worker actually exits and the
request evidence is durable; saturated requests fail immediately and do not overwrite the in-flight
check's persisted evidence. Late worker results cannot publish success. The check does not call
`List`, create roots, or invoke any adapter mutation. Bounded evidence includes invariant
`sideEffects=none`/`retrySafe=true`, is marked stale after an edit, and is required by checked
activation. The submitted R3-F1 correction validates evidence paths before probing, normalizes an
ordinary Future/Worker failure, and completes the response side of the capacity lease from one outer
`finally`, including repository-save failure. A failed Validated revision can be edited through the
same guided/raw Web path and returns to Draft for explicit revalidation and retry. Independent R3-F1
review accepted this exception-safe evidence/capacity correction on 2026-08-25. The submitted R4 Web
projection reads the existing revision-bound evidence from
`ConfigurationObjectService.revision_detail()` after reload and renders it independently of revision
status. Evidence is current only when revision ID, version, digest, and the persisted stale flag all
agree. Draft cannot run the check; revalidated stale evidence cannot checked-activate; exact current
passed evidence may enable checked activation. Rendering performs no API mutation or background
retry. Independent R4-F1 review accepted this persistence/reload boundary and the corrected shared
Web selection: only enabled libraries referencing Local Storage can expose the Run action, and those
same objects supply the request IDs. Activation itself remains repository-only; after activation the
existing Preview Job endpoint carries the immutable snapshot pin. R5-F1 and the 2026-08-25 Final
Closure Audit accepted the combined production-entry proof: revision A is setup-checked and
checked-activated, its DryRun Preview Job is queued, behavior-distinct revision B becomes Active,
and the Worker still loads A's saved document before workflow construction. Job, Task, TaskItem, and
Result retain A's ID/digest and A-derived destination while source/target trees remain unchanged.
Remote setup remains TARGET. Recognition policy editing and offline Strategy Test were subsequently
accepted in Phase 22.4; MetadataPolicy managed editing/offline resolution was accepted in Phase
22.5-A. Managed live Provider testing/candidate explanation and its F1 correction were accepted in
Phase 22.5-B. Candidate confirmation and its F1/F2 corrections were accepted in Phase 22.5-C.
Phase 22.5-D same-Provider managed live correction testing passed independent High re-review.
Phase 22.5-E is limited to one resolved correction's pinned DryRun continuation and passed
independent High re-review at `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`, closing Phase 22.5;
Slice 22.6 has closed the bounded managed Naming/Classification/Organize journey: Local-only
destination precheck for one RecognitionType and one to eight samples routed to one destination
Storage, independent row recovery, collision and capability verdicts, and checked activation
without mutation or execution authority. Remote
SMB/OpenList/S3 destination precheck, mutation-based capability probing, multiple RecognitionTypes
or destination Storages per request, known-media duplicate detection, attachment precheck and
absolute mounted-path display remain TARGET; Provider switching, generic Task resume and unattended
execute also remain later work. The broader Files/Media manual-organize journey remains planned,
while per-item Task recovery was subsequently delivered by Slice 23.

## Configuration architecture: TARGET (partially implemented; remaining work explicit)

The long-term architecture is a single activation authority:

```text
Managed Configuration
→ Draft
→ Validate / Test
→ Validated version
→ Explicit atomic Activate
→ Immutable Runtime Snapshot
→ Engine
```

Managed object edits create a new Draft version and never mutate the Active snapshot. Validation and
test evidence bind to the exact draft version; any later edit invalidates that evidence. Activation
validates the complete reference graph, atomically publishes one immutable snapshot, records its
version/digest and Before/After audit, and leaves the previous Active snapshot intact on failure.
Runtime components must receive or resolve that snapshot explicitly. Web/API status showing Active
must be generated from the same snapshot identity actually consumed by engines and workers.

JSON remains supported for bootstrap, import/export, migration, disaster recovery input, and support
bundles. After managed activation exists, JSON is not a second live authority and editing a
file cannot silently diverge from or replace Active configuration. Credentials remain outside normal
configuration payloads and are resolved only at the infrastructure boundary.

Phase 22.2/22.2R implements much of the lifecycle, integrity, recovery boundary, and work-pinning
foundation for whole-document revisions. F1 fixed repeated invalid-Active bypass, Scheduler
same-snapshot loading, and valid older pinned continuation. F2 now implements atomic resident API
binding and actionable missing/corrupt pinned-revision failures and has passed independent review.
This migration is not the complete configuration product.
Remote/provider and policy object CRUD, broader dependency impact editing, provider connectivity tests,
export/import UI, secret-store integration, and user administration remain future work. Until an explicit activation exists, the product labels JSON as
`JSON_BOOTSTRAP`; after activation the managed snapshot is the sole workflow authority and JSON is
not consulted for fallback.

## Per-item recovery architecture: CURRENT (Slice 23; PASS / CLOSED)

```text
Task
→ TaskItem
→ Processing Checkpoint
→ exact-version Recovery Request
→ analysis-only Recovery Continuation / bounded Batch
→ existing Worker pipeline
→ linked DryRun Task / Result
```

`ProcessingCheckpointService` projects one bounded restart-safe view from the persisted Task,
TaskItem, Result, operation-effect evidence, review/conflict, audit, recovery-request and continuation
records. The projection reports the durable/raw stage, Storage-relative source, immutable snapshot
ID/digest, plan/result links, completed and uncertain effects, blocker, error category, retry safety
and permitted actions. Its version is a digest of the bounded persisted facts. Missing legacy facts
remain unknown; read paths redact unsafe paths and never construct Storage or Provider objects.

`RecoveryAdmissionService` is the shared exact-version write gate used by API/Web and the adapted
retry/ignore/re-plan entry points. SQLite re-projects the checkpoint inside an IMMEDIATE transaction,
then atomically validates Task/item/source/snapshot identity, action admissibility and active-request
uniqueness before recording the request and its existing action-specific transition. A later Active
snapshot is never substituted. Requests grant only `task_recovery`; no historical execute,
overwrite, delete, cleanup or rollback authority is copied.

An admitted safe pre-mutation request may create one `RECOVERY_CONTINUATION` AutomationJob pinned to
the same immutable snapshot, limited to one item and always `execute_authorized=false`. Job,
continuation and optional batch-child linkage commit together. The Worker validates current request,
source ownership, checkpoint boundary, snapshot equality, fencing/cancellation and one-item scope,
then calls the existing `MediaOrganizerService.process_file(..., execute=False)`. Completion links a
new DryRun Task/TaskItem/Result while retaining the original evidence. Uncertain or unknown effects
fail closed to investigation; terminal success/skipped/DryRun/ignored items receive no replay action.

`RecoveryBatchContinuationService` composes that same single-item gate for a deterministic maximum
of 100 selections. Each child owns independent checkpoint/request/continuation/Job and terminal or
waiting evidence; the persisted parent read model derives queued, running, completed, failed,
cancelled, refused, waiting, recovered, ignored and unchanged counts after reload. A persist-failed
`selected` child can be explicitly resumed without touching already admitted or terminal siblings.
Authenticated API and Operator Web use these same services, RBAC and confirmations and link the
source checkpoint, blocker, Job and new Task/Result.

## Manual organize Preview architecture: CURRENT (Task 24.3)

The manual-organize Preview boundary is a separate immutable projection over an existing intent:

```text
ManualOrganizeIntent
  -> version/source/choice/snapshot validation
  -> Parser -> Recognition -> Metadata -> Naming -> Classification
  -> OrganizePlanner + attachment/capability/conflict observation
  -> ManualOrganizePreview / ManualPreviewItem
```

`ManualOrganizePreviewService` accepts only an open intent, bounded item IDs, optimistic intent and
item versions, and the intent's pinned snapshot identity. It reloads the exact managed runtime
snapshot, uses the existing Strategy/Metadata/Planner authorities, and converts their results to
bounded provider-neutral JSON evidence. The input fingerprint includes the source identity,
normalized choice, snapshot identity, source-linked pipeline evidence, review links, and conflict
decisions. The plan fingerprint covers the persisted exact plan projection. RecognitionType remains
the selected type even when its downstream NamingPolicy, ClassificationPolicy, and OrganizePolicy
are A.

SQLite publishes the parent and all child records in one `BEGIN IMMEDIATE` transaction. Re-preview
supersedes only the selected item identities; historical parent/child rows remain reloadable and
unselected siblings retain their independent state. Source or choice updates and cancellation
mark current Preview rows stale in the same intent transaction. Preview reads compare the durable
fingerprint with current indexed/source-linked facts and mark stale without rebuilding a plan.
The two Preview tables are additive and idempotent on the existing Runtime schema marker `27`, so
older databases receive them on open without rewriting prior Task, Result, review, or intent rows.

The API and Operator Web call this same application service and projection. The Web requires an
explicit confirmation and renders per-item plans, blockers, evidence, conflicts, capability gaps,
and the fresh-Preview recovery action. Preview wraps every configured Storage adapter in a
read-only guard, performs only analysis reads, never creates a Task/Job/authorization, and never
calls `OrganizerExecutor`; execution admission remains a separate future boundary.

## Exact reviewed manual execution architecture: CURRENT (Task 24.4)

Task 24.4 extends the Preview boundary with a distinct, explicit execution authority. The execution
service accepts only a current Preview ID, bounded selected item IDs, exact optimistic versions,
snapshot identity, the persisted plan fingerprints, actor/permission and a positive confirmation.
It reconstructs executor input from the immutable Preview projection; request bodies cannot provide a
source, destination, operation, Provider payload or adapter call. The authority is auditable, bounded
by the selected set, expires, and is consumed once.

Admission is a SQLite `BEGIN IMMEDIATE` transaction. It rechecks the open intent, current Preview and
each selected Preview item, source identity, choice, plan fingerprint, snapshot, conflict decision,
capability verdict and destructive-operation authority. It creates the exact existing `Task`/
`TaskItem` scope and the companion manual-execution/effect records in that transaction, then acquires
the normalized source, destination and attachment path locks. A failed or concurrent admission creates
no execution Task and does not mutate media Storage. The existing `FileOperationLockRepository` is
also used as the execution fence; locks are released only after the item Result and effect evidence
are durable.

For an admitted item, `ManualOrganizeExecutionService` reloads the pinned runtime and exact persisted
plan, revalidates current Storage capability and destination/conflict state, and invokes
`OrganizerExecutor` with `execute=True`. `OrganizerExecutor` remains the only mutation boundary for
Move, Copy, HardLink, SoftLink, attachment transfer and configured source-directory cleanup. Link
operations verify their link type rather than treating a symlink's lstat size as media size;
unsupported capabilities fail explicitly and never fall back. RecognitionType C and its downstream
A policy ownership are copied into Result evidence without changing the recognition identity.

Each item gets its own durable Result, completed-operation/effect evidence, status, error, effect
certainty and TaskItem checkpoint. Known successful effects are recorded as verified; pre-mutation
failure remains eligible only for the existing safe checkpoint recovery when its pinned snapshot is
resolvable, while partial/unknown mutation is investigation-only. A process restart reloads the
authority, execution, Task/TaskItem, Result, effect and checkpoint projection; it never replays an
admitted mutation or silently rebuilds the plan. API and Operator Web use this same service and
projection, including the separate manual-execution permission and two explicit confirmation steps.

Scheduled unattended execution, automatic crash replay, universal compensation, remote setup and
provider switching remain outside this boundary.

### Remaining recovery TARGET

Slice 23 does not implement automatic replay of uncertain media mutation, cross-run compensation or
historical rollback beyond the existing per-invocation Organizer rollback, distributed Task leases,
forced interruption of external calls, automatic crash replay, Metadata Provider switching, the
broader Files/Media manual-organize journey or scheduled unattended real execution. These are not
dependencies of the current checkpoint and DryRun continuation path. OrganizerExecutor remains the
only Storage mutation boundary, and any future real continuation must independently satisfy current
authority, Storage capability and conflict/destructive-operation gates.
