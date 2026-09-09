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
    → Slice 34 — Review & Recovery Workspace
    → Slice 35 — Configuration Administration
    → Slice 36 — V2 Parity, Accessibility & Legacy UI Retirement
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
`/api/v1/*` behavior. All Slice 30 outcomes are accepted; Slices 31–36 retain ownership of the
later operator-surface migrations and cutover.

The current V2 frontend foundation is a client-side React/TypeScript SPA built with Vite, TanStack
Router and TanStack Query, organized feature-first with a central typed API boundary and
project-owned design system foundation. Vitest and React Testing Library cover unit/component
behavior, with a Playwright browser-smoke foundation. The Vite output is served by the existing
MediaFlow Python application; Node is build/development tooling only and is never a production
server runtime.

The V2 program preserves the current `/api/v1/*` authority, Python application/domain behavior,
API-principal Bearer-token model, memory-only browser token handling, RBAC and all explicit execution
and OrganizerExecutor safety gates. The existing V1 Operator UI remains available during migration;
its final `/ui` retirement is deferred to Slice 36.

V1 keeps the environment-owned API-principal Bearer-token authentication model and explicit RBAC.
It does not provide a built-in username/password database, cookie session, OIDC or implicit
reverse-proxy identity. Token rotation and secret injection are deployment responsibilities.

### Interactive execution authorization: CURRENT V1 and V2 TARGET

**CURRENT V1:** interactive remote execution may use a separately issued, short-lived, single-use
execution authorization token. The operator or automation issues it through the local CLI, receives
the raw value once and supplies it to an authenticated API request through the
`X-MediaFlow-Execution-Token` header. The digest is persisted, admission and consumption are atomic,
and the normal API-principal Bearer token alone is insufficient mutation authority. The current V1
Jobs Web UI does not expose this remote-execution token journey as a complete operator flow. This
mechanism may continue to support API automation, local administration, debugging, compatibility
and emergency/support workflows.

**V2 TARGET:** the routine operator-facing Web journey must not require manual CLI issuance or raw-
token transfer. A later Operations Slice may provide a Web-native, short-lived/scoped execution
grant, execution unlock, step-up authorization or equivalent interaction, automatically bound by
the backend to the reviewed operation and permitted scope. This target does not select an endpoint,
schema, table, grant identifier, WebAuthn/PIN mechanism or other concrete design.

Both CURRENT and TARGET preserve backend RBAC and permission enforcement, bounded execution
authority, limits, audit, immutable configuration binding, stale/concurrent fencing, explicit
mutation intent and OrganizerExecutor-only Storage mutation. Uncertain mutation is not
automatically replayed. Slice 33 owns the future Operations Workspace implementation boundary unless
A later changes the Roadmap.

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

## Persistence

The runtime SQLite repository persists FileIndex, Tasks, TaskItems, Results, locks, review queues,
manual intents/previews/executions, Automation Definitions/Jobs/occurrences, notification delivery,
execution authority, security audit and operational logs. The configuration SQLite repository
persists managed revisions, object/reference state, activation/test evidence and configuration audits.
The implementation currently declares runtime schema `33`, configuration-management schema `10` and
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
contains the selected source identity, choices, pinned configuration, destination, operation,
attachments, conflict and capability evidence. A separate one-shot authority and explicit
confirmation admits only the exact selected Preview items.

Admission rechecks versions, source identity, fingerprints, conflicts, capabilities and authority in
one SQLite transaction, then acquires source/destination/attachment locks. The execution service
reconstructs the plan from persisted Preview data; request bodies cannot supply arbitrary paths,
operations or provider payloads. `OrganizerExecutor` performs the actual mutation and persists each
effect/result/checkpoint independently.

The current file-level execute endpoint calls that bounded execution service synchronously inside
the API request, even though durable Task/TaskItem/Result records are created. Files and FileIndex
provide bounded file/ResourceLibrary Scan, exact Preview and explicit manual Organize entry points;
the general Jobs API also supports bounded `scan`, `preview` and `organize` submission. Scan and
Preview remain DryRun/zero-mutation operations. Organize requires the existing separate one-shot
execution authority and explicit confirmation; the existing revalidation, RBAC, conflict and
capability gates remain in force, and only `OrganizerExecutor` mutates Storage.

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

## TARGET architecture

### V1.x/V2 deferrals

Provider switching and additional production providers, built-in users/sessions/OIDC, general Secret
Store/Docker Secrets integration, automatic uncertain-mutation replay, historical rollback and
specialized notification channels remain outside the V1 architecture above.
