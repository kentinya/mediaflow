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

This is a recoverable-task foundation, not a background worker. Live pause/control, scheduler,
distributed leases, and automatic crash replay remain deferred. See [`docs/roadmap.md`](roadmap.md).

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
existing workflow entry point, which creates normal Task and Result records. Cancellation is
pending-only. The service accepts no organize/execute job, so preview preserves DryRun's zero-
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

List/stat results are converted to domain `StorageEntry` objects. Read, write, and same-share copy
are streamed in one MiB chunks. Move uses native SMB rename/replace and never falls back to copy
plus delete. Delete handles files and empty directories but is not recursive. HardLink and SoftLink
are deliberately unsupported, report false capabilities, and never fall back to another operation.

SMB client failures map to domain Storage error codes for missing paths, permissions, conflicts,
connection failure/loss, authentication, timeout, I/O, and unknown errors. Public messages contain
only the operation and error category, not credentials or arbitrary SDK exception text.

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
server's finite pages. Reads follow the `raw_url`/proxy/redirect choice made by OpenList and expose a
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
from `Storage.read` to `Storage.write`; cross-storage MOVE uses the same copy, verifies the target,
and only then calls source `delete`. A failure before any completed mutation is FAILED; a failure
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

## Deferred work

Phase 15 persists organize conflicts as `waiting_confirm` records in SQLite. `ConflictResolver`
applies configured Skip/Rename decisions without mutation; Manual and Overwrite enter the durable
confirmation queue. Rename uses bounded `Storage.exists` probes and produces a replacement plan.
Overwrite requires an overwrite-enabled policy plus a fresh persisted high-risk confirmation.
Only OrganizerExecutor consumes the resulting authorized plan and remains the sole mutation
boundary. Decision audit records are append-only, and invalid destinations cannot be overridden.

Metadata and classification review/resolution APIs are complete; a graphical UI remains deferred.
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

Phase 19.4 replaces the Phase 19.3 first-page-only limitation with forward keyset pagination.
Tasks/Jobs use newest-first `(created_at, ID)` ordering; TaskItems/Results retain oldest-first
processing order. SQLite applies the composite boundary before `LIMIT`, never OFFSET or prior-row
enumeration. The established cursor boundary therefore remains stable when newer records arrive.

The opaque URL-safe cursor has a version, resource kind, timezone-aware ordering timestamp, and
stable record ID. Decoding strictly bounds length and validates Base64, JSON schema, version, kind,
timestamp, and ID. It contains no media or secret fields and query strings remain excluded from
security audit. TaskItem and Result cursors advance independently. The UI exposes explicit Next and
first-page refresh only; backward navigation, totals, and live polling remain deferred.

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
