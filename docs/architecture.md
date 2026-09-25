# Architecture

This document describes the architecture implemented at the current repository head and separates
remaining V1.x/V2 targets from current behavior. It is organized by component and boundary; development
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

The V1 release line is version `1.0.0`; Slices 26 through 29 form its released baseline.

Slices 26, 27, 28 and 29 are PASS / CLOSED. The V1 business-capability sequence is:

```text
Slice 26 — Web-first fresh setup and Storage
    → Slice 27 — Manual operations and file lifecycle
    → Slice 28 — Web-first configuration and operations administration
    → Slice 29 — Docker production self-hosted release
```

These are vertical product slices. They do not authorize a rewrite of the closed processing engine
or a split into independent API/database/frontend products.

## V2 program architecture

V2 is a release/program level on `main`, not one mega-Slice. Its independently reviewable roadmap is:

```text
Slice 30 — V2 Frontend Platform & Architecture
    → Slice 31 — Operator Shell & Information Architecture
    → Slice 32 — Library & Files Experience
    → Slice 33 — Operations Workspace
    → Slice 37 — Files Workspace, Common File Management and V2 Shell
    → Slice 38 — MediaLibrary Files Workspace and Route Separation (PASS / CLOSED)
```

Slice 30 is `PASS / CLOSED` under the A-owned Contract in [`SLICE.md`](../SLICE.md), with Base
`7c7c602c6531c60ddf2d6678857e2ef76c3860b6` and Implementation Head
`6953b87afa09e61ff62ffea5eb2a9a7d96c55492`. Task 30.1 delivered the first proving unit of the
architecture below: the `web/` React/TypeScript/Vite source boundary with TanStack Router and
TanStack Query, a central typed API client with memory-only Bearer-token auth, the read-only
Dashboard route, and Python static serving of the built artifact at `/ui-v2/` beside the unchanged
V1 `/ui`. Vitest, React Testing Library and a minimal Playwright path cover it. Task 30.2
delivered the production packaging boundary of the same architecture: the Docker build is
multi-stage, running `npm ci` from the committed `web/package-lock.json` and `npm run build` in a
Node build stage and copying only the built static files into the final Python runtime image at
`/opt/mediaflow/web/dist`, where `MEDIAFLOW_UI_V2_ASSET_ROOT` binds the exact artifact directory
consumed by the running Python process. The runtime image keeps no Node executable, npm,
`node_modules`, frontend source, development server, SSR process, CDN dependency or second HTTP
service, and the API service serves `/ui-v2/` and hashed assets beside the unchanged V1 `/ui` and
`/api/v1/*` behavior. All Slice 30 outcomes are accepted; later Slices retain ownership of the
business-surface migrations and cutover after the shared shell boundary.

Slice 31 is `PASS / CLOSED` at Base `2e7aceb50750fb54689ab26bfd1214b8e36c25f8` and Implementation
Head `45cb1d4cdda6cf46a6d6699600bc4a4563efc06b`. Task 31.1 established the centralized information
architecture, responsive shell, migration routes and browser proof. Task 31.2 completed the
route/authentication lifecycle: a feature-independent authentication/route-continuation boundary
ensures that an operator entering a supported deep route can connect through the memory-only
principal boundary, continue to the intended safe route,
and recover from absent/rejected authority (401), forbidden access (403), unavailable data or an
unknown route without losing shell context. Dashboard consumes the shared lifecycle rather than
retaining a competing authentication flow.

Slice 32 is `PASS / CLOSED` at Base `76de3f60e223131a8b7db97a566d0ceaadd9b2a0` and Implementation
Head `ad8ba3b272e683ab2bb1627b4df8f60aa49d6e99`. It composes the existing Python Active
configuration, Storage Browser, FileIndex catalog/detail and by-source resolution into a read-only
V2 Library route family. Frontend-owned strict models and the central authenticated API/query
boundary consume bounded `/api/v1/*` projections; they do not create a second business authority.
Stable directional paging stays in the authoritative FileIndex repository, physical/indexed links
require an exact Active Storage and enabled ResourceLibrary binding, and detail evidence is bounded,
allowlisted and redacted. All Library requests are GET-only; V1 `/ui`, operational mutations and
OrganizerExecutor ownership remain unchanged.

Slice 33's accepted implementation is at Base `827c36b410687e41b1da53ba6475d8c03a47dbfd` and final
Implementation Head `e4a5f7696d1742f7b6ef2a784c3b5d234b707d08`. Its post-closure Worker correction
preserves exact current-source authority across the resident Worker boundary: the reviewed Preview
persists Storage ID, source path and Storage-derived source fingerprint, and the Worker validates the
live source by opening that Storage and calling `stat(source_path)` directly. Missing live sources or
fingerprint mismatches fail closed before mutation; routine FileIndex rescans do not cause execution
to re-resolve `file_id -> FileIndex -> path`. No accepted Operations behavior is removed.
It composes the existing Python application,
persistence and `/api/v1/*` authority into the V2 Operations route family: actionable Dashboard,
durable Tasks/Jobs, bounded Scan/Preview, exact Web-native manual Organize, Automation definitions,
schedules, grants and occurrences, and Webhook definitions, tests and delivery recovery. The
frontend owns typed presentation and exact requests, not business decisions or mutation authority.

The current V2 frontend foundation is a client-side React/TypeScript SPA built with Vite, TanStack
Router and TanStack Query, organized feature-first with a central typed API boundary and
project-owned design system foundation. Vitest and React Testing Library cover unit/component
behavior, with a Playwright browser-smoke foundation. The Vite output is served by the existing
MediaFlow Python application; Node is build/development tooling only and is never a production
server runtime.

The V2 program preserves the current `/api/v1/*` authority, Python application/domain behavior,
API-principal Bearer-token model, memory-only browser token handling, RBAC and all explicit execution
and OrganizerExecutor safety gates. The existing V1 Operator UI remains available during migration.
Slice 37 is PASS / CLOSED at Base `b507edba167f5af3af8c53bfcf1417ba4fefddf4` and Implementation
Head `aa54854c442d117c7eb23ae9800045c423db1368`. It replaced the former V2 shell presentation with
the shared light shell in the canonical Files reference, completed Files common bounded file
management, removed the direct browser Upload/Download vertical from the current surface,
corrected formal `library/path` destination parity, and repaired exact Storage path identity. The
Files page does not render recognition-result or organize-status feedback. The manual Organize Web
choice editor now derives NamingPolicy, ClassificationPolicy and OrganizePolicy from the selected
RecognitionType under the pinned snapshot, while preserving type identity and failing closed on an
unavailable mapping. Non-Files business-surface migrations and final cutover remain outside the
closed Slice; existing non-Files route behavior is retained inside the replacement shell. Slice 38
has delivered its MediaLibrary route/browse/command baseline through the recorded implementation
head, including page-local ResourceLibrary/MediaLibrary editing.

V1 keeps the environment-owned API-principal Bearer-token authentication model and explicit RBAC.
It does not provide a built-in username/password database, cookie session, OIDC or implicit
reverse-proxy identity. Token rotation and secret injection are deployment responsibilities.

### Interactive execution authorization: CURRENT V1 and V2

**CURRENT V1:** interactive remote execution may use a separately issued, short-lived, single-use
execution authorization token. The operator or automation issues it through the local CLI, receives
the raw value once and supplies it to an authenticated API request through the
`X-MediaFlow-Execution-Token` header. The digest is persisted, admission and consumption are atomic,
and the normal API-principal Bearer token alone is insufficient mutation authority. The current V1
Jobs Web UI does not expose this remote-execution token journey as a complete operator flow. This
mechanism may continue to support API automation, local administration, debugging, compatibility
and emergency/support workflows.

**CURRENT V2:** the routine operator-facing Web journey does not require CLI issuance or raw-token
transfer. After the operator reviews an exact durable Preview and confirms the selected items and
any permitted destructive effects, the backend creates server-held, short-lived, single-use
authority bound to the authenticated principal, Preview/configuration/item set and effect scope.
Admission and authority consumption are atomic; the resident Worker later claims the durable
execution under a fence before OrganizerExecutor may perform Storage mutation. The browser neither
receives nor submits the raw authority or its digest.

Both V1 and V2 preserve backend RBAC and permission enforcement, bounded execution
authority, limits, audit, immutable configuration binding, stale/concurrent fencing, explicit
mutation intent and OrganizerExecutor-only Storage mutation. Uncertain mutation is not
automatically replayed. The V1 token mechanism may continue for API automation, local
administration, debugging, compatibility and emergency/support workflows.

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
the exact managed revision, Storage, directory and page request. It remains a read-only bounded
Storage browser, while the separate File Catalog is the FileIndex surface.

For Local Storage, `rootPath` is an absolute path visible inside the execution environment. In a
self-hosted Docker deployment the path must be explicitly bind-mounted with the intended
read-only/read-write permission and container UID/GID ownership or access. Unmapped host paths,
host `/`, the Docker socket and arbitrary host filesystem access are unsupported. The browser
does not expose the Local root itself to the client and rejects paths outside that configured
Storage root.

## Configuration authority and runtime binding

On the compatibility path before managed activation, the JSON document is the runtime authority and
is labelled `JSON_BOOTSTRAP`. A fresh instance may instead start from the minimal management-only
bootstrap, which loads only the SQLite locator and environment-owned API-principal definitions;
that state has no workflow runtime authority until an operator creates, validates and activates a
managed revision. Both bootstrap paths keep configuration status and replacement recovery available
without treating incomplete workflow content as Active.

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

The Files-page `+ 添加资源库` action is a bounded convenience over this same authority. Its final
`保存` command uses the save-time Active snapshot as the candidate base and composes successor
configuration, ResourceLibrary validation, applicable checked evidence, activation and runtime
rebinding inside the backend. The operator does not manage the intermediate Draft/Validated states
in this page-local flow. A validation, dependency, Storage-check, activation or runtime-load
failure rejects the command and leaves the previous Active pointer and runtime authority intact.
The general Configuration surface continues to expose the explicit Draft/Validate/Activate journey.

## Persistence

The runtime SQLite repository persists FileIndex, Tasks, TaskItems, Results, locks, review queues,
manual intents/previews/executions, Automation Definitions/Jobs/occurrences, notification delivery,
execution authority, security audit and operational logs. The configuration SQLite repository
persists managed revisions, object/reference state, activation/test evidence and configuration audits.
The implementation currently declares runtime schema `34`, configuration-management schema `10` and
managed document schema `1`. These are compatibility markers, not feature statuses.

Runtime database initialization is additive and refuses a newer unsupported schema. Backup, restore,
migration rehearsal and upgrade preflight are read-only or explicitly isolated boundaries; they do
not construct Storage/Provider workflows or grant media execution authority.

## File index and libraries

`ResourceLibrary` defines where source media is discovered, including Storage identity, relative
path, extension/include/exclude rules, depth, scan mode and file stability policy. Scanning is
read-only and records durable FileIndex state. Temporary/actively written files remain excluded by
configured stability rules.

The current Operator **FileIndex** page is a File Catalog over those indexed records, not a Storage
browser. `FileIndexRecord.scan_status` and `change` describe discovery/stability only; the separate
processing disposition is persisted on the current source occurrence. Storage-derived
occurrence/fingerprint evidence and historical occurrence rows bind TaskItem and Result records to
the observed occurrence, while path-only legacy rows are explicitly unverified. The FileIndex
projection exposes current versus historical Result relevance. Explicit Reprocess is an audited,
exact-occurrence admission marker for a later Scan/Preview workflow; it creates no Task, Provider
request or Storage mutation. File-/ResourceLibrary-scoped Scan and the manual processing workflow
use the same bounded current-source identity and authority rules.

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

Conflict/review decisions are persistence-only and do not execute media. The current Web carries the
operator from a resolved conflict or review through exact-source re-analysis, continuation admission
and the original Organize outcome. Successful siblings remain terminal and uncertain effects remain
investigation-only.

## Manual organize

Manual organization uses a durable intent and exact immutable Preview before execution. The Preview
contains the selected source identity, reviewed Storage ID, Storage-relative source path,
Storage-derived source fingerprint, choices, pinned configuration, destination, operation,
attachments, conflict and capability evidence. A separate one-shot authority and explicit
confirmation admits only the exact selected Preview items.

Admission rechecks versions, reviewed source fingerprint, conflicts, capabilities and authority in
one SQLite transaction, then acquires source/destination/attachment locks. Execution does not
resolve the source through FileIndex: the service reconstructs the plan from persisted Preview data,
opens the reviewed Storage ID, calls `stat(source_path)`, and compares the live Storage fingerprint
with `preview.source_fingerprint`. Missing sources and fingerprint mismatches fail closed before any
mutation; request bodies cannot supply arbitrary paths, operations or provider payloads.
`OrganizerExecutor` performs the actual mutation and persists each effect/result/checkpoint
independently.

The compatibility file-level execute endpoint calls that bounded execution service synchronously
inside the API request. The V2 Operations flow instead atomically admits an exact Preview selection
with server-held one-shot authority, returns a durable execution/Task identity, and lets the
resident processing Worker claim it under a persisted fence before any mutation. Legacy Files and
FileIndex provide separate bounded compatibility entry points, while the current V2
ResourceLibrary Files path uses live Storage for its exact Preview and explicit manual Organize
admission. The general Jobs API also supports bounded `scan`, `preview` and `organize` submission.
Scan and Preview remain DryRun/zero-mutation operations. Organize requires explicit confirmation
and the relevant destructive-effect permissions; revalidation, RBAC, conflict and capability gates
remain in force, and only `OrganizerExecutor` mutates Storage.

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

The embedded V1 Operator Web and the React/TypeScript V2 SPA are static UIs served by the same
Python application. V2 currently exposes Dashboard, Library and the Operations route family for
Tasks, Jobs, manual Scan/Preview/Organize, Automation and Notifications; Review/Recovery and general
Configuration remain explicit migration landings. Both UIs use the shared `/api/v1/*` application
authority. The browser holds the API token only in memory and does not provide built-in account
login.

The `api serve` HTTP listener uses `wsgiref.simple_server` and remains a development/trusted-loopback
boundary. Production Compose uses the explicitly selected `api serve-production` command with the
Waitress WSGI adapter. Neither path claims TLS termination, certificate management or public
Internet exposure; host binding and reverse-proxy trust remain deployment boundaries.

The resident processing Worker durably registers before claiming work, heartbeats while live,
records clean stop, binds to an immutable runtime snapshot and uses Worker identity plus a per-claim
fence token for completion. Authenticated API/Web expose bounded Worker registration, readiness,
owner heartbeat and stale/no-Worker recovery evidence separately from API process health. Claim
admission fails closed for stale lease, unsupported schema and incompatible snapshots, with explicit
queued continuation records preserving safe pinned recovery. The API process does not and must not
start, supervise or register a Worker subprocess implicitly.

## Notifications and operational logging

The notification layer contains a signed HTTPS Webhook transport, durable delivery Outbox, bounded
retry, delivery leases, dead-letter state and explicit requeue/replay actions. The current Web/API
surface manages Webhook definitions, event selection, deployment-owned secret references, exact-
revision bounded tests, delivery detail and per-delivery retry/requeue recovery without exposing
secret values or changing completed media work.

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

## Current Slice 26 delivery

Slice 26 delivered the management-only fresh bootstrap, first complete managed Draft through Web,
guided Local/SMB/OpenList/AWS S3/Cloudflare R2/generic S3-compatible configuration and read-only
tests, bounded Storage Browser/path selection, Local path recovery and first-runtime checked
activation. It did not add mutation-based capability probes or arbitrary host-path access.

## Current Slice 27 delivery

Slice 27 delivered the real Storage Files/FileIndex distinction, current-source lifecycle and
disposition, bounded manual Scan/Preview/Organize, conflict/review/recovery continuation, and
Processing Worker readiness and fenced ownership across the shared Application, Persistence, API and
Operator Web boundaries. These capabilities reuse the existing Storage abstraction, immutable Active
snapshot authority, Task/TaskItem/Result model and OrganizerExecutor mutation boundary.

## Current Slice 28 delivery

Slice 28 delivered the day-2 managed-configuration lifecycle and object-management IA, including a
natural Active-to-successor-Draft edit path, consistent create/copy/edit/enable/disable/delete and
reference recovery, forms-first editing with Advanced JSON/import/export as explicit support paths,
consumed System Settings, versioned secret-free configuration/result exchange and managed Webhook
definition/test/delivery recovery. These capabilities reuse the existing revision authority, RBAC,
redaction and immutable snapshot rules.

## Current Slice 29 delivery

Slice 29 packages one immutable image with independent Compose API, Worker, Scheduler and
Notification Worker services, production Waitress WSGI serving, explicit local `/data` persistence,
media bind mounts, non-root operation, liveness/management/business readiness, restart persistence,
fenced ownership, fail-closed backup/migration upgrade behavior and release-security validation.
The Jobs/Preview/Organize execution boundary remains explicit and OrganizerExecutor-only.

## Current Slice 32 delivery

Slice 32 adds the V2 Library landing, bounded Active Storage directory browser, FileIndex
catalog/search/filter/directional paging, strict detail/evidence projection and uniquely confirmed
physical/indexed navigation. It reuses managed Active snapshot, Storage and FileIndex/Application
ports and existing authenticated `/api/v1/*` reads. The frontend stores no domain authority or
credentials, renders no raw fingerprint/provider/private-path material, and exposes no Storage or
workflow mutation. Its accepted behavior remains historical and unchanged.

## Current Slice 33 delivery

Slice 33 adds the V2 daily Operations command center with actionable Dashboard links, filterable
Task/Job state and backend-advertised controls, bounded manual Scan and zero-mutation Preview,
Web-native exact manual Organize, Automation definition/schedule/grant/occurrence operation, and
Webhook definition/test/activation/delivery recovery. Long work returns durable identities and is
claimed by the resident Worker; independent item/delivery outcomes and bounded failure handoffs stay
visible. The final Worker correction reconstructs the exact pinned ResourceLibrary/Storage authority
from the admitted execution's immutable runtime snapshot and fails closed before mutation on missing,
stale or cross-authority evidence. The implementation preserves shared Python authority, exact Active
snapshot and revision binding, memory-only Bearer/RBAC, explicit mutation intent, no automatic
uncertain replay and OrganizerExecutor-only Storage mutation. Its accepted behavior remains
historical and unchanged.

## Slice 38 architecture — CURRENT delivered capability

### MediaLibrary file management and route separation

The delivered Slice 38 baseline exposes ResourceLibrary Files at `/ui-v2/resourcelib/files` and
MediaLibrary at `/ui-v2/medialib/files`; the old `/ui-v2/library/files` and `/ui-v2/library`
registrations use bounded route recovery. Media-scoped browse, direct commands and transfers resolve
MediaLibrary authority independently of ResourceLibrary authority. The delivered page-local edit
journey covers both library kinds.

Both pages reuse the shared shell and suitable presentation/command mechanisms. Each owns its
library selection, query/navigation state, form and allowed actions. The MediaLibrary path is:

```text
MediaLibrary ID + relative path
  -> exact Active MediaLibrary / Storage / root binding
  -> confined live Storage reads and bounded command admission
  -> OrganizerExecutor for explicit mutations
  -> durable per-item Task/result/recovery and refreshed live listing
```

Media-scoped `/api/v1/media-libraries/...` endpoints share application behavior with Web. Existing
resource-scoped APIs and Files Organize retain their semantics. Library kind must be unambiguous in
lookup, cursor/evidence binding, cache keys, transfer manifests, persisted execution and recovery;
equal IDs do not grant cross-kind authority. Historical ResourceLibrary work stays readable and
safely resumable. Resolve actual Storage paths to reject aliased self/descendant transfers. Only
narrowly required persistence changes belong to this Slice, with migration/recovery validation.

MediaLibrary Copy/Move uses MediaLibrary endpoints on both sides, within/across supported Storages.
Existing capabilities, evidence, conflicts, explicit destructive intent, snapshot pinning, Worker
fencing and non-replay remain mandatory. Files retains its existing ResourceLibrary transfers and
Organize-to-MediaLibrary pipeline. General cross-kind direct transfer is deferred. MediaLibrary
browsing does not use FileIndex/Result membership or invoke recognition, metadata or media Organize.

Page-local ResourceLibrary/MediaLibrary create/edit/removal composes existing managed validation,
references, applicable read-only evidence and atomic activation/runtime binding. Edit resolves one
exact Active object by immutable ID, merges only the focused fields while preserving unexposed
configuration, and rejects stale Active evidence before publication. It creates no media work or
physical directory and never migrates root contents. Failures preserve Active; configuration
removal preserves files. Broader object/ID migration and general configuration editing remain on
the existing Configuration surface. No card statistics, thumbnail collection/content requests,
new providers, stream inspection or FFmpeg/FFprobe are introduced.

### V1.x/V2 deferrals

Provider switching and additional production providers, built-in users/sessions/OIDC, general Secret
Store/Docker Secrets integration, automatic uncertain-mutation replay, historical rollback and
specialized notification channels remain outside the V1 architecture above.

## UI-V2 Files and Manual Organize authority update — 2026-09-13

UI-V2 Files now treats ResourceLibrary as the operator-facing authority. The normal Files path is:

ResourceLibrary -> configured Storage binding -> ResourceLibrary root path -> live Storage list/stat.

The browser supplies only `resourceLibraryId`, ResourceLibrary-relative `path`, and a server-issued
cursor. The server resolves the Active managed runtime, verifies the ResourceLibrary and backing
Storage are enabled, joins the ResourceLibrary root with the relative path, and reads through the
read-only Storage guard. `RuntimeFilesBrowserService` accepts a legacy `file_index` composition
argument for compatibility but intentionally does not consult it to enumerate or authorize the UI-V2
Files projection. The Files projection excludes FileIndex membership, `fileId`, occurrence,
fingerprint and other raw authority fields. It may include a bounded recognition/business-status
projection as display feedback. FileIndex remains a separate indexing and compatibility authority;
it is not the source of physical Files entries or execution authority.

UI-V2 manual organize admission now starts from ResourceLibrary source selection.  The normal single-file path is:

ResourceLibrary -> live Storage file -> zero-mutation Preview -> SourceIdentity + server OrganizePlan -> confirmed Task -> Worker -> live Storage revalidation -> OrganizerExecutor.

The Files page submits `scopeKind=file`, `resourceLibraryId` and `relativePath` to the
server-bound Preview route. `ManualOrganizePreviewService.create_current_from_storage` resolves
the Active runtime and bound Storage, calls `Storage.stat()`, creates SourceIdentity/fingerprint
evidence and calls `ManualOrganizeIntentService.create_from_sources`; no FileIndex row or `fileId`
lookup is involved. The zero-mutation planner persists the reviewed evidence. Execution validates
the reviewed source against live Storage and the persisted Preview identity; it does not
re-resolve the source through FileIndex. FileIndex-backed compatibility routes remain separate.

FileIndex is permitted on the Files path only for the bounded business-status/recognition display
projection. It must not determine physical listing membership, path validity, Preview source
identity, execution authorization or Storage capability. After each terminal Organize item result
is recorded, the application automatically synchronizes the known result/disposition to FileIndex.
If that synchronization fails, the index-sync failure is recorded independently and the system does
not replay any completed or uncertain Storage mutation.

## UI-V2 direct file-management authority update — 2026-09-14

The Files workspace adds deliberately short read and mutation paths for ordinary maintenance:

```text
selected Active ResourceLibrary source/destination
    -> live list/stat/read + capability/limit admission
       └─ mutation command
            -> OrganizerExecutor
            -> per-item audit/result
            -> refreshed live listing
            -> optional FileIndex display reconciliation
```

This boundary supports CreateDirectory, bounded text-file creation, Rename, Copy, Move, Delete,
bounded allowlisted text Read/Write for one item or a bounded selection. Direct browser Upload and
Download are outside the current Files surface; generic Storage/provider transfer primitives remain
available for supported backend workflows. It
does not run Scanner, Parser, Recognition, Metadata, Naming, Classification, the organize Planner,
organize Preview or execution-token review. The shorter journey does not create a second mutation authority: the
application enforces backend RBAC, selected Active source/destination bindings, relative-path
confinement, provider capability, item/depth/size limits, stale/conflict checks and explicit
Delete/Replace/Save intent. Only OrganizerExecutor invokes CreateDirectory/Copy/Move/Delete/Write.

Same-Storage Copy/Move uses advertised native capability without fallback. Cross-Storage Copy is an
explicit transfer. Cross-Storage Move is modeled as a visible compound operation with per-item
checkpoints:

```text
Copy destination -> verify destination -> delete source
```

Failed verification leaves the source intact. Failure after a verified copy records a partial
result and recovery rather than concealing two extant copies or replaying an uncertain deletion.
Bounded recursive/batch mutations use the existing Task system and independent item outcomes.
Delete may include bounded non-empty directories after a lightweight item/size impact summary and
one explicit confirmation, but ResourceLibrary roots and unbounded recursion are rejected.

Direct browser Upload/Download controls, routes and services are removed from the current Files
vertical. Arbitrary binary or media-content editing and arbitrary host paths remain outside this
boundary.

Live Storage is authoritative before and after each command. FileIndex may be reconciled to prevent
stale display feedback, but it never admits the command; reconciliation failure is recorded and
must never replay a completed or uncertain mutation.

Rename and Delete are fenced by the provider's own verifiable entry identity (Local:
`inode` + `ctime`; S3/R2: the object validator) together with the observed entry type, size and
`mtime`. Evidence issuance, command admission, Delete confirmation and the executor's last safe
boundary all re-read metadata only, so their cost never scales with file size and no entry content
is read to authorize or verify these two mutations. A provider that publishes no verifiable entry
identity (SMB, OpenList) fails closed with `files_direct_entry_identity_unavailable` before any Task
or Storage mutation instead of falling back to size, `mtime`, a content prefix or a full read. The
bounded allowlisted text Read/Write keeps its separate loaded-version digest fence, which is capped
by the bounded text size limit.

## UI-V2 Files and shared-shell contract update — 2026-09-14

Slice 37 uses [`docs/pics/文件页.png`](pics/文件页.png) as the sole `1536 x 1024` visual reference
for the Files route and shared V2 shell. One shared AppShell implementation must replace the former
dark horizontal chrome with the reference light left rail and top bar across every supported V2
route; the reference is not rendered as a nested Files card inside the old shell. Route identity,
memory-only authentication continuation, query ownership, backend calls and non-Files page-body
behavior remain unchanged even though their outer chrome changes.

The detailed Files layout, required copy/data, row command surfaces, open `添加资源库` drawer and
reference-aligned visual acceptance rules are in
[`docs/file-page-visual-spec.md`](file-page-visual-spec.md). Controlled pixel diffs are diagnostic;
the architecture does not require identical raster output when the specified structure, state and
interaction remain intact.
The frontend owns presentation and exact user intent only. It does not become Storage authority or
make FileIndex a physical-source/execution authority. Focused backend/application behavior for
ResourceLibrary save/activation, direct file commands and post-mutation index reconciliation is
part of the confirmed Files journey; unrelated business behavior remains unchanged.

## Slice 37 delivery — 2026-09-22

The current implementation delivered the Slice 37 Files journey across the shared V2 shell,
ResourceLibrary activation, live Storage browsing, bounded direct file commands, Storage-source
Organize continuation, formal `library/path` destination parity, truthful refresh/presentation and
exact Storage path identity plus exact FileIndex reconciliation.
The direct browser Upload/Download vertical was removed from the current surface while generic
Storage/provider transfer primitives remain available. The implementation preserves the single
Python authority and
OrganizerExecutor mutation boundary described above. The explicitly deferred binary/media editing,
unbounded operations, V1 cutover, broad non-Files redesign, new providers/identity systems,
universal rollback and automatic uncertain replay remain deferred. The Files page does not render
recognition-result or organize-status feedback; exact entry names and ResourceLibrary-relative paths
are preserved through the frontend projection, including boundary whitespace, and are never retried
as a trimmed sibling.
