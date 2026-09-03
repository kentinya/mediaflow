# Architecture

This document describes the architecture implemented at the current repository head and separates
remaining V1 targets from current behavior. It is organized by component and boundary; development
Phase, Fix and Task names are historical evidence, not architecture states.

## Structure and dependency direction

MediaFlow uses a ports-and-adapters layout:

```text
infrastructure adapters → domain ports ← application use cases
                                      ↓
                              API / Operator Web
```

`mediaflow.domain` owns immutable models, value objects and protocols. `mediaflow.application`
coordinates those ports and owns user journeys. `mediaflow.infrastructure` implements storage,
metadata, persistence, logging and transport adapters. `mediaflow.interfaces` exposes the shared
Application behavior through the authenticated API and embedded Operator Web.

The main dependency rule is that business code does not call filesystem, network Storage, SQLite or
provider SDK APIs directly. It uses domain interfaces and application services.

## V1 order and architecture decisions

The repository is at Slice 25 closure with Slice 26 active. Remaining V1 business capabilities are:

```text
Slice 26 — Web-first fresh setup and Storage completion
    → Slice 27 — Manual operations and file lifecycle
    → Slice 28 — Web-first configuration and operations administration
    → Slice 29 — Docker production self-hosted release
```

These are vertical product slices. They do not authorize a rewrite of the closed processing engine
or a split into independent API/database/frontend products.

V1 keeps the environment-owned API-principal Bearer-token authentication model and explicit RBAC.
It does not provide a built-in username/password database, cookie session, OIDC or implicit
reverse-proxy identity. Token rotation and secret injection are deployment responsibilities.

V1 uses the `MetadataProvider` abstraction with TMDB as the production provider. Provider switching,
additional production providers and arbitrary provider plugins are V1.x/V2 work. A missing or
invalid TMDB credential fails closed; it does not trigger an implicit provider fallback.

## Processing pipeline

The production path is:

```text
ResourceLibrary
  → Scan / FileIndex
  → Parse / optional NFO evidence
  → RecognitionRule
  → RecognitionType
  → RecognitionTypePolicy
  → MetadataPolicy / TMDB Provider
  → MediaIdentity
  → NamingPolicy
  → ClassificationPolicy / MediaLibrary
  → OrganizePolicy
  → OrganizePlan
  → OrganizerExecutor
  → TaskItem / Result / history / log
```

Scanner, Parser, Recognition, Metadata lookup, Naming, Classification and Planner are analysis
boundaries. They do not mutate Storage. `OrganizerExecutor` is the only application component that
may invoke mutating Storage operations.

Recognition returns only RecognitionType evidence. It never renames, moves, copies, deletes or
chooses a final library path. `RecognitionTypePolicy` separately resolves Metadata, Naming,
Classification and Organize policies. A type can reuse another type's downstream policies without
changing its identity; RecognitionType C remains C when it uses A's Naming/Classification/Organize
policies.

Technical tags such as resolution, source, codec, audio and HDR are filename/path observations. No
FFmpeg or FFprobe dependency or media-stream inspection is part of the architecture.

## Storage abstraction

The domain `Storage` port covers list, stat, exists, read, write, create directory, move, copy,
delete, hard link and soft link concepts. Each adapter reports explicit capabilities. Unsupported
operations fail with a stable error and never silently fall back to another operation.

Current infrastructure adapters are:

- `LocalStorage`, root-confined with logical relative paths and symlink escape protection;
- `SMBStorage`, behind an infrastructure-only SMB client boundary;
- `OpenListStorage`, behind an infrastructure-only HTTP client boundary;
- `S3Storage`, covering AWS S3, Cloudflare R2 and generic S3-compatible services.

Adapters normalize provider errors into domain Storage errors, redact credentials and apply their
own timeout, retry and streaming rules. Read-only checks use a guarded adapter view. Mutation is
never inferred from capability metadata and no production adapter is assumed to support every
operation.

### Storage and path semantics

`Storage.rootPath` belongs to the adapter. `ResourceLibrary.storagePath` and `MediaLibrary.rootPath`
are normalized paths relative to their referenced Storage. Plans retain Storage identity and logical
relative paths rather than host mount prefixes. Local roots may be host/container absolute paths;
remote roots are provider-specific logical roots.

The current runtime can load all supported Storage kinds from JSON. Managed Web/API guided setup
now exposes one provider-neutral, read-only bounded Storage Browser and directory picker for every
configured Storage kind. Its browser paths are Storage-relative and its continuation is bound to
the exact managed revision, Storage, directory and page request. It is a setup surface only; the
File Catalog remains a FileIndex surface until Slice 27.

For Local Storage, `rootPath` is an absolute path visible inside the execution environment. In a
self-hosted Docker deployment the path must be explicitly bind-mounted with the intended
read-only/read-write permission and container UID/GID ownership or access. Unmapped host paths,
host `/`, the Docker socket and arbitrary host filesystem access are unsupported. The browser
does not expose the Local root itself to the client and rejects paths outside that configured
Storage root.

## Configuration authority and runtime binding

Before managed activation, the compatibility JSON document is the runtime authority. It is labelled
`JSON_BOOTSTRAP`. The bootstrap boundary can independently load the SQLite locator and
environment-owned API-principal definitions so configuration status and replacement recovery remain
available while workflow configuration is unavailable.

Managed Configuration persists whole-document Draft, Validated, Active and Superseded revisions.
Object edits, references, evidence and audits are revision-bound. Activation is an atomic pointer
change only after validation and any checked-evidence requirements pass. Checked activation is
provider-neutral: every enabled Storage referenced by a ResourceLibrary or MediaLibrary needs a
current, passed, read-only per-Storage check; the Recognition Strategy Test and one read-only
destination precheck for the MediaLibrary destination must be current for every Storage kind. The
earlier Local-only setup check remains available as a Local diagnostic but is no longer the
activation authority. The previous Active remains available when replacement fails.

After activation, `ManagedConfigurationService` verifies the digest/schema/runtime load and builds an
immutable runtime binding containing revision ID, version and digest. API requests, Workers, Jobs and
scheduled occurrences use that binding or their persisted snapshot identity. A missing, corrupt,
schema-incompatible or runtime-invalid Active fails media work closed and never falls back to JSON.
Activation itself starts no scan, Job, Task, schedule occurrence or media mutation.

## Persistence

The runtime SQLite repository persists FileIndex, Tasks, TaskItems, Results, locks, review queues,
manual intents/previews/executions, Automation Definitions/Jobs/occurrences, notification delivery,
execution authority, security audit and operational logs. The configuration SQLite repository
persists managed revisions, object/reference state, activation/test evidence and configuration audits.
The implementation currently declares runtime schema `31`, configuration-management schema `10` and
managed document schema `1`. These are compatibility markers, not feature statuses.

Runtime database initialization is additive and refuses a newer unsupported schema. Backup, restore,
migration rehearsal and upgrade preflight are read-only or explicitly isolated boundaries; they do
not construct Storage/Provider workflows or grant media execution authority.

## File index and libraries

`ResourceLibrary` defines where source media is discovered, including Storage identity, relative
path, extension/include/exclude rules, depth, scan mode and file stability policy. Scanning is
read-only and records durable FileIndex state. Temporary/actively written files remain excluded by
configured stability rules.

The current Operator **Files** page is a File Catalog over those FileIndex records, not a Storage
browser. `FileIndexRecord.scan_status` and `change` describe discovery/stability only. File detail
can join TaskItems, Results, reviews and checkpoints by source Storage/path, but Result/TaskItem rows
do not bind to a distinct current source occurrence or content fingerprint. A changed file at the
same path retains the path-derived FileIndex ID, so prior processing outcome cannot yet be treated as
the current file's unified disposition without an additional identity/projection contract.

`MediaLibrary` defines a destination Storage and relative root. Classification selects the library
and relative path; Naming supplies directory and filename. The final target is composed from the
MediaLibrary root, classification path and naming path, with path safety checks before planning.

## Tasks, Results and processing recovery

Long-running work is represented by persisted Task and TaskItem records. Jobs are queue/admission
records; Tasks represent actual processing; Results and history record outcomes. Pause is cooperative
at media-item boundaries. Cancellation, retry and recovery are explicit and do not interrupt an
in-flight provider/Storage call or claim an unknown mutation was undone.

Each item has an independently persisted Processing Checkpoint with stage, pinned configuration
identity, known effects, effect certainty, failure category and next action. Safe recovery can
continue analysis-only stages or create bounded one-item/batch continuations. Successful siblings are
not replayed or hidden. Partial or uncertain mutation is investigation-only unless a separately
proven safe action is offered.

Conflict/review decisions are persistence-only and do not execute media. The current Web explicitly
reports that a saved decision does not resume the Task, but it does not carry the operator directly
from a resolved conflict to re-analysis, continuation admission and the original Organize outcome.
Legacy CLI Task resume remains a separate recovery route.

## Manual organize

Manual organization uses a durable intent and exact immutable Preview before execution. The Preview
contains the selected source identity, choices, pinned configuration, destination, operation,
attachments, conflict and capability evidence. A separate one-shot authority and explicit
confirmation admits only the exact selected Preview items.

Admission rechecks versions, source identity, fingerprints, conflicts, capabilities and authority in
one SQLite transaction, then acquires source/destination/attachment locks. The execution service
reconstructs the plan from persisted Preview data; request bodies cannot supply arbitrary paths,
operations or provider payloads. `OrganizerExecutor` performs the actual mutation and persists each
effect/result/checkpoint independently.

The current file-level execute endpoint calls that bounded execution service synchronously inside
the API request, even though durable Task/TaskItem/Result records are created. Repository-wide
manual organization remains a CLI workflow, while the general Job API admits only scan and preview.

## Automation and unattended execution

The current Automation Task Definition model is scoped to a configured ResourceLibrary and bounded
source path. Scheduler emits durable occurrences and AutomationJobs idempotently. Each Job pins the
Active snapshot at creation; the Worker runs the existing pipeline and records linked Task/TaskItem/
Result evidence.

Unattended authority is persistent, scoped, revocable and separate from schedule enablement. Preview
eligibility and authority are required before a due run may reach mutation. The Worker rechecks live
authority, scope, capabilities, conflicts and current snapshot at each mutation boundary. Revocation
blocks future mutation without rewriting completed effects. Uncertain mutation is not automatically
replayed.

## API and Operator Web

The API is a versioned WSGI application over shared application/repository services. It provides
authenticated configuration, files, tasks, jobs, reviews, manual organize, recovery, automation,
schedules, notifications, logs, dashboard, security audit and system status routes. RBAC is applied
at the shared service boundary; 401/403 behavior and Web/API projections are tested together.

The embedded Operator Web is a self-contained static UI served by the same application. It exposes
Dashboard, Files, Tasks, Jobs, Schedules, Automation, Notifications, Logs, conflict/review views,
Configuration and a bounded read-only System status view. The current UI holds the API token only in
browser memory. It does not provide built-in account login.

The current HTTP listener uses `wsgiref.simple_server` and is a development/trusted-loopback
boundary. It is not a production WSGI server and does not claim TLS termination, certificate
management or public Internet exposure.

The Worker uses a fenced per-running-Job claim token and refreshes that Job's `updated_at` when the
pipeline checks cancellation. There is no resident processing-Worker registration, idle heartbeat
or readiness projection. Consequently a Pending Job cannot distinguish normal queue delay from an
installation where only the API is running. The API process does not and must not start a Worker
subprocess implicitly.

## Notifications and operational logging

The notification layer contains a signed HTTPS Webhook transport, durable delivery Outbox, bounded
retry, delivery leases, dead-letter state and explicit requeue/replay actions. The current Web/API
surface can inspect delivery state, but Webhook definition management, configuration readiness and
delivery recovery as a complete operator journey are Slice 28 work.

Operational logs use bounded redacted records with TRACE/DEBUG/INFO/WARN/ERROR semantics. Security
and configuration audits are separate durable projections. Secret values, authorization headers,
cookies, API keys, passwords and arbitrary provider exception text do not cross public evidence or
logging boundaries.

## Safety boundaries

- Scanning, parsing, recognition, metadata lookup, naming, classification and planning are zero-mutation.
- DryRun/Preview runs the complete applicable analysis path but does not execute Storage mutation.
- Only `OrganizerExecutor` invokes mutating Storage methods.
- Overwrite and delete require explicit policy/authority; they are never silent.
- HardLink and SoftLink never fall back to Copy or Move.
- Local and logical remote paths are normalized and confined before access.
- API/Web reads and status pages do not create Jobs, invoke Providers or mutate Storage unless an
  explicit action says so.
- Secret references are allowed; secret values are not persisted in managed documents or evidence.

## Backup, restore and migration

SQLite backup uses online snapshot semantics and integrity verification. Restore is an explicit
non-overwriting operation into a controlled destination. Upgrade preflight and migration rehearsal
validate Python support, backup integrity, schema agreement and representative state without
changing the live database. Migration failure must leave the live authority untouched and fail
closed before work resumes.

## TARGET architecture

### Slice 26 target

Add management-only fresh bootstrap, first complete managed Draft through Web, guided SMB/OpenList/
AWS S3/R2/generic S3-compatible configuration and read-only tests, bounded Storage Browser/path
selection, Local path recovery and first-runtime activation without hand-authoring a full runtime
JSON document. Do not add mutation-based capability probes or arbitrary host-path access.

### Slice 27 target

Reuse the Slice 26 provider-neutral Storage Browser as the real configured-Storage **Files** entry
point while renaming the indexed catalog responsibility to **FileIndex**. Add a current-source
processing-disposition projection without overloading scan status, source occurrence/fingerprint
correlation, explicit duplicate-work admission and Reprocess, coherent file/ResourceLibrary
Scan/Preview/Organize manual actions, analysis-only Preview findings, real Organize
Attention/Conflict/Review/Recovery continuation and processing-Worker readiness. Preserve one-shot
manual authority, persistent revocable unattended authority, successful-sibling isolation,
uncertain-effect refusal and OrganizerExecutor-only mutation.

### Slice 28 target

Complete the day-2 managed-configuration lifecycle and object-management IA, including a natural
Active-to-new-Draft edit path, consistent create/copy/edit/enable/disable/delete/reference recovery,
forms-first editing and Advanced JSON/import/export. Add consumed System Settings, versioned
secret-free configuration/result import-export and complete managed Webhook
definition/test/delivery recovery. Reuse the current revision authority, RBAC, redaction and
immutable snapshot rules.

### Slice 29 target

Package one immutable image with independent Compose API, Worker, Scheduler and Notification Worker
services, a production WSGI server, explicit local `/data` persistence, media bind mounts, non-root
operation, liveness/readiness/business health, restart persistence and fail-closed backup/migration
upgrade behavior. Keep TLS, certificates, public exposure policy and proxy trust explicit deployment
boundaries.

### V1.x/V2 deferrals

Provider switching and additional production providers, built-in users/sessions/OIDC, general Secret
Store/Docker Secrets integration, automatic uncertain-mutation replay, historical rollback and
specialized notification channels remain outside the V1 architecture above.
