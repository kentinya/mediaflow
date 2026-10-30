# Architecture

This document owns component/dependency boundaries and distinguishes accepted CURRENT baselines
from TARGET design. [Progress](progress.md) owns closure facts; committed [SLICE.md](../SLICE.md)
owns scope. Slice45 is PASS / CLOSED: Task Center/typed recovery, shared live listing and
Scan/Preview/FileIndex retirement below are CURRENT. Slice43 is also PASS / CLOSED; its Automation
workspace/settings foundation remains accepted. Slice46 is PASS / CLOSED; its current amendments
below replace selected entry/query/intent behavior without changing prior acceptance or deferrals.
Detailed former delivery notes remain at `865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/architecture.md`.

## CURRENT — Slice46 presentation and work-query ownership

[Slice46](../SLICE.md) owns outcomes/acceptance; `V2-UX-004`, `V2-OPS-014–017`, `V2-FILES-007`
and `V2-AUTO-010/011` identify the accepted amendments after A final review on 2026-10-29.
Unchanged foundation contracts below remain current; this section owns the affected layer boundaries.

- **Presentation:** shared action components supply readable states. Files owns ordinary-command
  results and durable local reopening; Task Center owns organizing progress and four-type recovery.
  Exact preparation/unknown-request readback remains accessible without the global discovery block.
- **Navigation context:** shared sidebar destinations are ordinary page navigation. Files does not
  derive or carry `returnOps` from a task-center list or an earlier Files visit. Explicit task,
  preparation and organizing links retain their own bounded return state. Files consumes that state
  from the router's committed search through the existing bounded parser, so same-route navigation
  clears the visible return action without a stale mount-time copy. This state conveys no authority.
- **Admission:** reuse Task/Worker/pipeline. Explicit Files organizing admits before business
  readiness. Direct sources use verified duplicate/excluded-extension checks; folder tasks precede
  bounded traversal, with configured primary-type filtering and atomic per-source item admission.
  Do not hold database transactions across Storage I/O. Complete bounds checks precede effects.
- **Intent and planning:** manual summary/selected confirmation is inside the task; Automation
  enable/enabled-successor publication supplies scheduled intent and Run once supplies one-run intent.
  Remove independent-grant dependencies and the normal initial Automation confirmation. Backend
  plans, pins, source/capability/permission checks, destructive intent and fences still govern effects.
- **Work queries:** scope supported organizing commands and durable Job/Task links before grouping,
  paging, counts or detail. All eight views and pending counts share that authorized population;
  browsers cannot filter mixed pages locally. Attention is the distinct four-type union and its
  required human recovery steps. Normal manual WaitingConfirm stays in Running/All, not Attention.
  Exact verified recovery may project Completed without rewriting attempts or double-counting runs.
  Other terminal failures retain factual read-only history; shared administrative recovery remains.
- **Local readback:** use existing durable Tasks/results/claims/audit, bound to principal/library kind/
  source/pin. Browser hints are neither authority nor the sole index. The centered status modal
  reopens work without cancellation, replay, a new queue or universal retry/undo authority.
- **Automation lifecycle:** reconcile confirmed own Save before further Enabled commands; retain peer
  conflict/input/unknown-outcome handling. Check enable/publication intent and permissions through
  every entry. Disabling/removal stops future due admission and unperformed scheduled effects at
  cooperative boundaries. Disabled Run once remains schedule-independent. Retain occurrence/run
  idempotency, immutable admitted pins and historical analysis/grant/failure evidence without replay.
- **Stability and bounds:** scheduled execution and Run once keep the existing shared organizing
  pipeline's real checks and conditional bounded wait/re-scan (RO-5/AC-18), work-scoped observations
  and continuation. Add no cross-run observation or failed-item retry mechanism. Keep Run once's
  `min(definition itemLimit, 100)` primary bound and traversal/evidence budgets.

Storage stays behind ports; only OrganizerExecutor mutates. Successful/uncertain effects never
replay; healthy empty is no-work, while unavailable or incomplete scope is not empty/success.
No second catalog, queue, execution/recovery engine or broader file authority is introduced.

## CURRENT — Admitted transfer Worker lifetime (Slice 39 implementation)

`_files_transfer_worker_context` installs both ResourceLibrary and MediaLibrary transfer consumers
before the first Active configuration exists. The resident runner atomically claims only commands it
advertises, then reconstructs a per-attempt application boundary from the admitted Task's persisted
library-kind command, revision ID and digest. Published superseded revisions remain valid task pins;
current Active is only the authority for new admission and never substitutes for an older pin.
Missing, corrupt or temporarily unusable pins return to the durable queue with bounded recovery
evidence and zero new Storage mutation.

Reconstruction and provider calls run under the existing claim token and lease keeper. The keeper
also renews the resident registration heartbeat, while mutation fences, persisted checkpoints and
uncertainty resolution continue to prevent duplicate or automatic uncertain replay. No queue,
OrganizerExecutor or direct-command authority was replaced.

The API separates service liveness, registration/heartbeat/DB/schema readiness and per-command work readiness.
Report current Active availability independently from support for older admitted snapshots. The
container Worker check verifies a live schema-compatible registration advertising both transfer
commands; it does not confuse no business Active with a dead consumer. API/Web transfer state uses
the same bounded readiness facts and explains waiting.
All health projections remain read-only and make no provider calls or Storage mutation probes.

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

V1 `1.0.0` and its accepted capability boundaries are recorded in [Release](release.md) and
[Progress](progress.md). Vertical business Slices do not authorize a processing-engine rewrite or
independent competing API/database/frontend products.

## V2 program architecture

`web/` is a feature-first React/TypeScript/Vite SPA with TanStack Router/Query, strict frontend-owned
models and a central authenticated API/query boundary. Python domain/application services and
`/api/v1/*` remain authoritative; presentation/cache never owns business decisions, pins or mutation.

A Node build stage runs `npm ci` from `web/package-lock.json` and `npm run build`. Only static
output enters the Python runtime at `/opt/mediaflow/web/dist`, selected by deployment-owned
`MEDIAFLOW_UI_V2_ASSET_ROOT`. No Node/npm/source/dev server/SSR/CDN or second production HTTP service.
Python serves `/ui-v2/` alongside V1 `/ui` and API; build/asset failure never silently serves stale work.
See [Deployment](deployment.md#v2-frontend-artifact-and-serving) for serving/security details.

The shared responsive AppShell owns route/auth continuation, bounded return context and permission/
unavailable/not-found recovery. Tokens remain memory-only; reject 401 authority and clear its queries,
while 403 preserves authenticated identity. Exact path identity survives typed normalization, including
boundary whitespace; navigation/cache cannot confer scope or rewrite an entry's name.

API-principal Bearer/RBAC, exact immutable Active/pinned work, explicit effect authority, audit,
claim/lease/fence and completed/uncertain non-replay remain unchanged. V1 does not add a password DB,
cookie session, OIDC or implicit proxy identity. TMDB stays behind MetadataProvider; unavailable
credentials fail closed with no implicit Provider fallback. Closed shell/page/engine milestones and
frozen/closed Slice status is maintained in [Roadmap](roadmap.md).

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
transfer. Files manual execution and four-type recovery require an exact durable organizing plan
and confirmation of the selected items and any permitted destructive effects. The backend creates
server-held, short-lived, single-use
authority bound to the authenticated principal, plan/configuration/item set and effect scope.
Admission and authority consumption are atomic; the resident Worker later claims the durable
execution under a fence before OrganizerExecutor may perform Storage mutation. The browser neither
receives nor submits the raw authority or its digest. Automation instead obtains scoped scheduled
intent from checked Enabled publication, or one-run intent from the explicit Run once command,
under V2-AUTO-010/011 below. These entry points still require exact backend plans/checks before effects.

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
  → bounded Scan / Discovery with work-scoped source evidence
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

Optional same-directory Kodi/Jellyfin-style NFO uses bounded read-only Storage discovery/reads,
rejects DTD/ENTITY and oversized XML, normalizes movie/show/season/episode and Provider/external-ID
evidence, and retains conflicts with filename evidence. NFO neither generates files nor creates a
verified metadata identity by itself.

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
Storage browser. Library-level live browsing is shared with CLI/Files/MediaLibrary; FileIndex is absent.

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

## CURRENT — Empty business runtime and resident configuration lifecycle

Slice 40 delivers this boundary at Implementation Head
`7805fa09d540fdeb5f0b39a5e3ac39c8c5ff7bb7`. At its Base the starter Draft contained empty business
collections, but strict strategy/runtime loading rejected them; V2 Settings was a migration landing,
Scheduler/Notification startup loaded workflow configuration, Notification targets were constructed
at startup and Compose required media mounts. The delivered implementation removes those setup
dependencies while preserving the transfer-specific resident reconstruction above.

The delivered boundary separates three facts: a structurally valid configuration graph, the exact
published immutable Active snapshot, and capability readiness for a command/scope. An empty graph satisfies
the first two after explicit activation, with no fabricated Recognition or policy objects. Every
populated object and declared reference still validates. Runtime construction must represent absent
capabilities without exceptions or development defaults. Command admission returns bounded
unconfigured/unready reasons; a browse/transfer path does not acquire media-pipeline dependencies.

The shared application authority computes applicability for both Settings activation and business
page successors: validate all populated objects; require exact Storage evidence for applicable
enabled library bindings, Recognition tests for applicable declared recognition chains, destination
prechecks for applicable configured targets/chains, and existing Automation/Webhook checks when
relevant. Missing capability is distinct from a broken declared dependency. Inapplicable checks
cannot be fabricated as passed; applicable stale/failed evidence still blocks atomic publication.

Native `/ui-v2/configuration` owns explicit first-Draft create/resume/activate, labelled Active/Draft
JSON, portable secret-free export and schema/field-allowlisted editing for supported fields absent
elsewhere. Read/navigation creates no Draft or work. JSON defaults to runtime-consumed Active, never
cache or a replacement Draft. Database locator and principal/role/token authority stay deployment
owned and cannot be changed by managed edits or imported portable configuration. Export excludes
that authority while retaining all portable supported settings and safe secret references. Existing
published snapshot identities remain verifiable; this is no permission to rewrite historical pins.

All three resident services initialize their process/infrastructure boundary independently of media
configuration. Worker retains advertised commands and resolves each admitted immutable work context;
Scheduler obtains current valid snapshot and schedule/admission data together before emission;
Notification Worker obtains current eligible delivery configuration without replacing durable target
identity or weakening leases/recovery. Configuration failure pauses affected work with bounded
reasons and no stale-cache fallback. Current Active governs new admission; intact older admitted
pins remain valid independently of current Active. Activation alone starts no media work or delivery.

Process liveness, DB/schema/registration/heartbeat readiness and command/pin work readiness remain
separate. Supported fresh Compose needs bootstrap/admin credentials and durable data but no media
mounts. Explicit Local Storage mounts/permissions become prerequisites only when Local is used;
mount changes remain deployment operations. Infrastructure health must allow normal unconfigured
waiting without presenting Scheduler/notification work as ready. Recoverable configuration/DB faults
retain resident processes and durable work; schema incompatibility remains fail-closed under the
explicit upgrade/recovery boundary. No API process supervision or new scheduler/queue is introduced.

Backend RBAC, exact successor/concurrency/evidence, audit/redaction, published pins, revocable
authority, lease/fence ownership, OrganizerExecutor-only mutation and uncertain-effect recovery stay
mandatory. Deployment/restart-only settings cannot be shown as hot-consumed. Acceptance proves
actual no-Active→empty Active→configured operation without resident process restart, including
controlled scheduling/delivery and transfer regression. This capability does not remove V1 or migrate
every policy/Review/Recovery workspace.

## CURRENT — V2 organizing rules workspace (Slice 41)

```text
/ui-v2/rules focused Save
  → exact Active + object candidate
  → shared object/reference/audit/concurrency services
  → whole-document validation + applicable evidence
  → atomic publication/runtime binding
  → existing Files / Operations / Automation / API / CLI consumers

explicit object test / complete-flow test
  → exact bounded non-Active candidate and sample
  → shared production engine → evidence only
```

`RulesWorkspaceCommandService` composes `ConfigurationObjectService` and
`ManagedConfigurationService`; generic revision/object APIs remain shared. Family-local analysis
uses `stage_analysis_candidate`/`RulesObjectAnalysisService`; compatibility complete analysis retains
`stage_preview_candidate`. Save constructs its own focused successor and never publishes sibling
Draft edits. The API enforces READ/configuration/activation permissions and serializes runtime
preparation with atomic publication. A failure preserves prior Active and correctable input;
unknown publication is reconciled by reading authority before another submission.

The eight inventories cover Overview, type binding, types, rules and Metadata/Naming/Classification/
Organize policies. Default is full-width inventory; Add/Copy explicitly opens a create drawer and
Edit a full-page route. Search/navigation creates no Draft, Provider call or work. Forms may retain
correctable tab-scoped values, never credentials or Active/execution authority. Unavailable impact
evidence blocks removal. Backend-legal IDs share one grammar across API/navigation/static entry;
only allowlisted edit routes accept a file-like final ID, not arbitrary dotted assets/traversal.

Production priority/score/ambiguity/stop-on-match and one enabled binding per type remain unchanged.
C keeps its identity under A policy reuse. Offline tests use pure engines; explicit live Metadata
calls only the configured Provider. Evidence binds revision/version/digest and goes stale on edits;
analysis grants neither publication nor execution. Save uses shared applicability without forcing
unrelated empty families. Detailed operator inputs/results are in
[Configuration](configuration.md#native-v2-organizing-rules-management) and
[Product Experience](product-experience.md#recognition-and-rules).

## CURRENT — Object-scoped Rules analysis and complete-flow separation

Family-local Web tests use `RulesObjectAnalysisService` and the authenticated
`/api/v1/operations/rules/analysis/{family}` routes. `stage_analysis_candidate` captures the submitted
object in a non-Active revision from the exact observed Active identity; object field/identity and
necessary-reference validation precedes analysis. It does not require a whole-runtime load merely
to test one object. Results bind family, candidate/revision/digest, purpose, sample and context;
relevant edits or Active changes invalidate freshness. Python retains RBAC, audit, concurrency and
policy authority. Analysis changes no Active pointer and creates no executable work.

RecognitionType definition needs no sample or downstream binding. Optional associated-rule
analysis uses only its bounded relevant set; absent rules are inapplicable. RecognitionRule reuses
production Parser/condition evaluation, reports bounded expected/actual condition truth including
non-match, and stops before downstream policy resolution. It does not force a type or claim that
one rule wins global competition. Binding analysis checks its type, uniqueness and four references.
Offline Metadata checks its own settings without Provider construction or credentials; explicit
live testing uses that candidate policy through the Provider port. Typed Naming and Classification
samples reuse the pure production engines; Classification validates its own destination references.
Organize explains effects, permissions and required capabilities without fabricating observed
physical readiness. Local offline analysis performs zero Provider and media Storage I/O.

Rules Overview's separately labelled `完整流程检查` uses the exact current Active and the shared
complete pipeline, including real recognition competition and policy resolution. It reports
missing prerequisites and labels supplied offline synthetic identity; explicit live Metadata
intent remains separate. Necessary destination observations are bounded read-only Storage calls.
Save still independently validates the whole successor and applicable publication evidence before
atomic activation. Local evidence grants neither publication nor execution. Historical full-test
API behavior/evidence, immutable snapshots and admitted Task/Job/Automation pins retain their
original scope. No alternate domain evaluator, runtime authority or Storage mutator is introduced.

The Rules workspace owns its content title/description and read-only refresh; its shared topbar
contains account/notification controls. Overview has no inventory search; each of the seven
inventories keeps one local search and its existing state filter. Normal refresh retains the
current section, filters and unsaved form input. The shared authorized-read boundary still owns
authentication and read failures; it does not present cached data as a successful refresh.
Normal workspace chrome omits the Active sequence and Settings handoff; exact Active publication
checks remain authoritative, diagnostics stay in Settings, and unavailable configuration retains
its allowlisted Settings return context. Category cards, inventory layouts, explicit Add/copy
drawers and full-page Edit retain their existing behavior. Styles are scoped to Rules; shared
shell navigation/authentication and other business routes retain their behavior.

## Persistence

The runtime SQLite repository persists Tasks, TaskItems, Results, locks, review queues,
organizing intents/plans/executions, work-scoped discovery/stability/source evidence,
Automation Definitions/Jobs/occurrences, notification delivery,
execution authority, security audit and operational logs. The configuration SQLite repository
persists managed revisions, object/reference state, activation/test evidence and configuration audits.
Compatibility versions are declared by the runtime/configuration repositories and managed-document
loader; inspect those constants rather than treating a copied schema number as a feature status.

Runtime database initialization is additive and refuses a newer unsupported schema. Backup, restore,
migration rehearsal and upgrade preflight are read-only or explicitly isolated boundaries; they do
not construct Storage/Provider workflows or grant media execution authority.

## Libraries and work-scoped source evidence

`ResourceLibrary` defines where source media is discovered, including Storage identity, relative
path, extension/include/exclude rules, depth and file stability policy. Internal discovery is
read-only; durable observations and source identities belong only to explicit work. Temporary/actively
written files remain excluded by configured rules, including real elapsed unchanged-size observation.

FileIndex and its global occurrence/disposition catalog, repositories, product surfaces, schema and
sync/reprocess/repair paths are absent. Shared library browsing reads bounded Storage list/stat,
never Task/Result membership, and creates no observations or work. Explicit work retains exact
Storage/path/metadata/fingerprint, plan/version/pin, claims/locks and known/uncertain effects for
admission/revalidation/recovery; these are not a substitute global file directory. Results do not
permanently suppress a later new source merely because its path matches. No old-index production
migration or automatic user-data clear/drop/rebuild is introduced.

`MediaLibrary` defines a destination Storage and relative root. Classification selects the library
and relative path; Naming supplies directory and filename. The final target is composed from the
MediaLibrary root, classification path and naming path, with path safety checks before planning.

A revised classification rule carries `mediaLibraryId` and one safe relative `path`; neither the
MediaLibrary display name nor its ID contributes a path segment. A rule created under the earlier
contract additionally carries a `library` prefix, and the runtime composes
`root/library/path/naming` for it so an existing snapshot, preview, plan, pin or result keeps its
original meaning. The two contracts are distinguished by the presence of that prefix, so a
published revised successor is a deliberate operator conversion rather than a schema change. A
rule whose explicit `mediaLibraryId` is missing is never resolved from its display name.

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

## Accepted foundation — V2 Operations and Tasks Workspace (Slice 42)

The existing Job/Task/TaskItem/Result, manual execution and recovery services remain execution
authority. A shared Python application projection joins only explicit durable links into one
operator-visible run. Pre-Task queued/failed admission and standalone Tasks stay visible; linked
Job/Task is counted once, while separate Automation occurrences and recovery attempts retain their
history. Queue completion cannot override Task/item outcome. This is a read model, not a new domain
Task object, queue or lifecycle state machine.

```text
V2 Operations inventory / selected detail / records / task-linked recovery
  -> typed authenticated query and command boundary
  -> Python run projection + existing lifecycle / review / recovery admission
  -> existing Job / Task / TaskItem / Result / audit / log repositories
  -> explicit safe continuation -> resident Worker -> OrganizerExecutor
```

Repositories supply bounded deterministic text/safe-scope/status/kind/time queries and aggregate
counts from the same authorized population and consistent read basis. Cursors bind query and
authorization context. No browser merge of independently paged Tasks/Jobs, page-only counts or
reading global logs to find one task. SQLite reads the page and aggregates in the same read
transaction. Additive schema40–42 indexes and `operations_run_display` retain bounded admission
display context without rewriting legacy rows or creating authority. Names and scopes derive from
durable admission or the pinned snapshot, never silently from current Active; missing legacy
evidence remains explicitly unavailable.

Progress is projected per work kind from durable evidence, independently of success rate. Unknown
discovery totals remain unknown; primary item counts reconcile, while discovery errors and attachment steps
remain separate. Waiting/ignored/uncertain items do not become successes. Details compose per-item
plan/step/result/checkpoint and bounded linked logs/audit; result truth does not depend on logs.
The existing secret-free result-package service remains export authority.

Creation reuses live ResourceLibrary Files selection, exact intent/Preview and existing explicit
manual execution admission, preserving contextual return to the selected run. FileIndex is not
physical source authority; MediaLibrary is not a new organizing source. Slice45 supersedes the
separate Preview product and its routes; supported Task/Job links and authentication stay intact.

`ScopeContinuationService` durably admits supported safely paused asynchronous work to the
existing queue. Schema43 `scope_continuations` links the original Task, exact admitted command,
remaining scope, budget and immutable pin to one continuation Job and its eventual Task. The
resident Worker reuses existing source revalidation, locks/leases/fences and checkpoint accounting;
HTTP does not run the long work or shell out to CLI. Continue excludes successful/ignored/uncertain
effects and rechecks applicable current authority. Persisted `execute_authorized` cannot reissue
consumed one-shot authority or bypass withdrawn scheduled intent/current permission checks. A changed plan or insufficient
authority returns to native exact Preview and explicit execution intent. Schema44's nullable manual
Preview origin-Task link preserves that continuation history without granting execution authority.

`TaskItemRecoveryService` composes existing checkpoint/review/recovery boundaries for the native
task-linked Recognition/Metadata/Classification/conflict forms.
Decision persistence is non-executing. Explicit bounded analysis and any later exact mutation
admission remain separate authority boundaries even when safe non-mutating steps are composed.
Mixed recovery batches preserve independent accepted/refused outcomes and link original item,
decision, continuation, Preview/execution and Result. Unknown effects remain investigation-only;
retired direct file retry/re-recognition/rematch/re-plan APIs stay retired.

Bounded active-work polling and manual refresh are read-only; unknown mutation outcomes are queried
before another explicit command. API/Web share permission/version/duplicate checks, redaction,
readiness and safe recovery behavior. No additional scheduler, Worker supervisor, Provider, global
Review inbox, history cleanup, universal rollback or automatic uncertain replay was introduced by42.
Slice45 adds the typed cross-Task lists below. These are accepted foundation facts at Implementation Head
`ce3fc2a3e70d40279fa725b5d7dc838d11123980`, reviewed by A on 2026-10-06.

## CURRENT — Task Center query, summary confirmation and typed recovery (Slice45)

[The Task Center specification](task-center-page-spec.md), stable `V2-OPS-009–012` and the committed
Contract own complete page/journey acceptance. Compose existing authorities:

```text
eight organizing views → typed query/command boundary
→ authorized admitted-organizing Task/Job/item/problem/checkpoint projection
→ bounded preparation → exact in-context summary → separate confirmation
→ atomic admission → resident Worker → OrganizerExecutor
```

All eight views combine their server-defined population with the local-calendar creation-day
range converted to UTC `from`/`to` (the `to` boundary covers the final microsecond of the day).
They omit removed keyword/source/status/command/attention filters and extra list problem predicates.
Exact run/problem-file location and detail filters remain separate from those list conditions.
Management-API consumers keep their existing filters; the time condition, rows, total, statistics
and cursor stay bound to one read snapshot. Manual refresh owns a local busy lifetime over its
bounded reads, including active detail reads; in-flight same-query polling can be joined.
Background polling never drives the manual busy indicator. Normal refresh preserves visible
content and valid context while rendering real changes; read/auth failures retain the shared
authoritative boundary.

Query before grouping/paging; bind cursors/counts to the authorized consistent population. Group each
problem by durable Task/run links; current problems, effects and lifecycle remain distinct. Never
infer links from labels/times, count pending automatically as human attention, or hide pre-Task failures.
Recovery uses existing decisions/checkpoints/continuations, retaining siblings/history and immutable
pins. Save/analysis grants no mutation; confirmation binds exact sources/plans/subset/effect scope.
Material change needs a fresh summary. Unknown submissions reconcile, never automatically resubmit.
No second queue, lifecycle, configuration or recovery engine. Exact internal organizing analysis/plan
records remain under their real responsibilities; the standalone Preview product exits under
V2-OPS-013 below. Organizing DryRun and shared Rules/configuration checks stay supported.

Slice46 narrows this CURRENT population and surface: center membership is proven by persisted admission
or a durable lineage/retry relation (an admitted Files Task or organize execution intent in its
discovery/analysis/confirmation stages, a supported organizing Job, and every continuation it really
owns), so a standalone analysis-only CLI DryRun and its analysis successors are administrative history
rather than center work. A continuation Job joins only through the exact persisted relation whose
source Task is itself in the admitted organizing population; its command family or produced Task alone
is never membership proof. The four types keep a first-attempt responsibility until the exact chain
reaches a confirmed follow-up; a technical failure leaves them and stays a read-only factual entry, and
the overall recovery-complete projection appears only when every necessary item carries its own
verified follow-up. Each run item publishes that same four-type/technical-history decision, so batch
selection and a reopened saved batch never turn a sibling's business problem into a generic technical
recovery entry. The retired mixed Task/Job collections keep their management APIs but no V2 list;
their deep links resolve an organizing identity into the exact center run and an ordinary identity into
its proven library page.

Scan is absent on first deployment, including definition modes and dedicated compatibility guards:
ordinary route/argument/shared type validation rejects before discovery/admission/authority. Shared
Scanner/filtering/real elapsed observation/planning remain inside supported workflows, without a
manual Scan prerequisite. No old Scan migration/history/takeover obligation or runtime/media clearing.
Supported same-version restart/results/pins/claims/non-replay remain required and validated.

## CURRENT — FileIndex retirement and shared live listing (Slice45)

[The FileIndex retirement design](file-index-retirement-spec.md) owns `V2-FILES-005/006` and complete
consumer/removal acceptance. CLI, ResourceLibrary Files and MediaLibrary resolve the same exact Active
library kind/ID/root through shared bounded live Storage list/stat behavior. Browsing persists no
catalog/observations/work, grants no authority and calls no Provider/Hash/mutation.

Global index/occurrence/disposition tables, repositories/stand-ins, product APIs/CLI,
initialization, sync/reprocess/repair and all actual consumers are removed, without a renamed cache
or no-op repository. Exact source/plan/pin/observation/results/locks remain bounded to explicit work;
reopen/recovery cannot replay known or uncertain effects. Fresh deployments have no index schema;
no old-index migration/dual-write/API compatibility and no automatic clear/drop/rebuild of user data.
Necessary shared Automation coupling may be cleaned without preserving43 UI or resuming its redesign.

Continuation cursors for the shared live listing are stateless and authenticated with one
deployment-internal key generated create-if-absent in the managed configuration store. The key is
internal metadata (not business configuration, not part of an Active revision, never portable or
exported) so a cursor issued by one CLI/API process stays verifiable by a later process. A strictly
read-only listing reads the key without creating or upgrading the store and refuses an uninitialized
store explicitly rather than minting a one-off process key.

## CURRENT — Standalone Preview retirement and shared analysis (Slice45)

[The Preview retirement design](preview-retirement-spec.md) owns `V2-OPS-013` / RO-8. Use the Scan
first-deployment standard: no standalone Preview Web/V1/API/CLI/aliases/help, Job/Task/command,
scheduled/definition-bound dispatch/retry/continuation, exclusive schema/services/repositories,
composition or compatibility/retirement layer. Old inputs ordinarily reject under normal auth and
shared supported-type validation before Storage/Provider/admission/authority; no conversion to Organize.

Web creation/Files/recovery and CLI organize without --execute call the same shared Organize DryRun
application analysis/planning behavior, retaining each entrance's actual scope/pin/policy choices.
API calls the application service directly; it does not spawn the CLI or add another analysis engine.
Web flow: Organize DryRun -> persist complete immutable source/configuration/plan/version evidence -> project
same-page summary -> exact explicit authority/admission -> revalidate the confirmed plan/source/permission
-> existing Worker/OrganizerExecutor/Result. Summary text alone is not an execution plan; material
source/plan changes require updated analysis/summary and fresh confirmation.
CLI organize without --execute and Rules/configuration/Automation preflight reuse real planning.
Preserve current candidate/definition/scope/permission boundaries, elapsed stability, findings,
attachments, capabilities and source revalidation. Analysis grants no permission and creates no
formal execution waiting/recovery backlog. Plan publication, pins/claims/fences and non-replay remain.

Shared exact-plan and recovery/authority records remain under organizing/Task responsibilities.
Internal `manual_previews` names and organize-plan API paths describe fixed plan data, not an
independently runnable Preview product. Long analysis uses the existing discovery Worker and durable
publication fence; no second queue/engine or automatic authority is introduced. Analysis-only
findings do not create formal execution blockers; delayed publication after accepted cancellation
cannot create a new confirmable plan.

No old Preview migration/takeover/history/cancel/export/V1-parity framework; no runtime/media clear or
automatic rebuild. Fresh deployments contain no independent Preview schema, while supported organizing
work reopens and recovers safely. These Slice45 contracts passed final review; necessary merged43
coupling cleanup did not itself accept the broader43 workspace; that was accepted separately.

## Manual organize

Manual organization uses a durable intent and exact immutable organizing plan before execution. The plan
contains the selected source identity, reviewed Storage ID, Storage-relative source path,
Storage-derived source fingerprint, choices, pinned configuration, destination, operation,
attachments, conflict and capability evidence. A separate one-shot authority and explicit
confirmation admits only the exact selected plan items.

Admission rechecks versions, reviewed source fingerprint, conflicts, capabilities and authority in
one SQLite transaction, then acquires source/destination/attachment locks. Execution does not
resolve the source through a catalog: the service reconstructs the plan from persisted organizing data,
opens the reviewed Storage ID, calls `stat(source_path)`, and compares the live Storage fingerprint
with `preview.source_fingerprint`. Missing sources and fingerprint mismatches fail closed before any
mutation; request bodies cannot supply arbitrary paths, operations or provider payloads.
`OrganizerExecutor` performs the actual mutation and persists each effect/result/checkpoint
independently.

Explicit manual-authorization API endpoints retain their bounded execution service. The V2 Operations
flow atomically admits an exact plan selection
with server-held one-shot authority, returns a durable execution/Task identity, and lets the
resident processing Worker claim it under a persisted fence before any mutation. V2 ResourceLibrary
Files uses live Storage for exact preparation and explicit manual Organize admission; indexed
compatibility entry points are removed. The general Jobs API admits only supported `organize`
submissions with its explicit execute/permission/one-shot-authority boundary. CLI organize without
--execute and Web preparation remain zero-mutation analysis. Execution requires explicit confirmation
and the relevant destructive-effect permissions; revalidation, RBAC, conflict and capability gates
remain in force, and only `OrganizerExecutor` mutates Storage.

## CURRENT — Bounded folder discovery and safe restart

ResourceLibrary Files list/grid admits folder or mixed selections to
`MediaDiscoveryService`, the resident discovery Worker and additive SQLite discovery/observation
records. Admission pins actor, library kind/ID, Storage/root and immutable configuration; it
reconciles equivalent open scopes independently of recent-list windows. Native status/progress,
findings, exclusions, waiting/read errors and cooperative controls precede explicit Freeze into the
existing manual intent, exact Preview and separately confirmed OrganizerExecutor execution.
MediaLibrary is not an organizing source. Discovery neither uses FileIndex for authority nor
calls Providers or mutates media.

The concrete bounds are 100 selected scopes, 100 primary sources, 10,000 visited entries,
1,000 directories, 2,000 page fetches, 100 entries per page, safety depth 32 and 600 active seconds.
Provider entries/cursors and exact relative paths are confined and deduplicated; metadata calls
stay outside SQLite write transactions. The pinned production configuration loader and shared
pure filters apply extension/include/exclude/depth/stability rules to automatic folder expansion at
every entrance. A directly selected file is instead the operator's own inclusion decision: it is
admitted unless it is explicitly excluded for that exact file (the built-in temporary/download
suffixes or a configured extension exclusion) or outside the configured depth. A suffix merely
absent from the configured allowlist, an include-rule miss and a non-extension exclude/match rule
therefore keep their unchanged automatic meaning without becoming an additional manual veto. The
same deliberate rule governs the expansion of a folder the operator selected by hand: inside it the
*one* retained automatic file filter is the ResourceLibrary's configured primary-media extension set
(video by default), so pictures, subtitles and NFO cannot become independent primaries merely because
they sat in the selected folder, artwork-off never promotes them, and the existing other-same-stem
attachment setting keeps working. Automatic walks (Scanner, definition-bound Run once, remaining-scope
recovery) keep the complete include/exclude/match filtering unchanged; the distinction is carried by
the durable admission mode of the record, not by a global weakening of the shared predicates. A
refusal of one deliberately selected item is that item's own durable `refusedEntries` outcome with its
bounded reason and next action, never a veto on its eligible siblings; structural, RBAC, root and
budget validation still refuse the whole request, and a selection in which nothing is admissible is
refused with its first item's reason instead of admitting empty work.
Folder
participation, safety/traversal budgets and real stability are unaffected.
Size stability is re-observed after real elapsed time; waiting releases the claim until its due
observation rather than consuming idle budgets or busy-looping. Explicit and walked regular-file
observations share the existing same-directory attachment matcher under the retained main's actual
pinned default manual policy before counting/freeze. Trailers remain attachments across selection,
paging and Preview; no parent directory outside the admitted scope is enumerated to associate them.

Ownership/version fences preserve accepted controls and reject stale-owner publication. Material
entry/depth/time/primary refusals remain durable and cannot expose an executable first-N prefix.
Isolated read errors preserve known sources for explicitly acknowledged subset review. Finalize
atomically creates one linked intent with its discovery transition; repeated/concurrent calls
cannot orphan or duplicate authority. Legal long source paths retain exact identity through the
manual handoff while run/search projections remain bounded.

Normal acknowledged Pause/Continue and cancellation are supported. If a crash/control race or
incompatible old record prevents provable continuation of unfrozen discovery, native recovery
preserves history/findings, settles/fences that attempt and offers deliberate distinct new
discovery. Lost admission responses recover a proved original request or remain unresolved with
Operations inspection; they never guess a newer root/pin or automatically resubmit. Guaranteed
seamless continuity across activation changes, every legacy duplicate and arbitrary crash/control
combinations remains deferred. Frozen pins and completed/uncertain media effects are never repinned
or automatically replayed. Actual schema-38→45 and old schema-45 migration/reopen evidence retains
frozen/file-only/discovery history; unsupported unfinished work has the safe-stop/new-discovery path.

### CURRENT — Files-admitted organizing Task and verified source ownership (Slice46)

Explicit Files 整理 commits the pinned queued `manual_organize` Task and its discovery record in one
transaction before traversal, Provider/business decisions or plan readiness. The Task's organizing
admission marker proves center membership; it is not permission to mutate. Manual execution still
requires the exact reviewed summary and selected confirmation. Discovery owns bounded read-only
work, TaskItems own their real findings/decisions, and only OrganizerExecutor mutates after all checks.

Task state follows discovery/stability/analysis and controls. A completed/partial walk stays unfinished
while decisions or initial confirmation remain; failed/cancelled work retains its cause. Later
progress never reopens a terminal execution. One accepted manual work is counted once across its
linked discovery/analysis/execution records. Exact verified per-item recovery may project Completed
without rewriting original failed attempts; ignored/skipped/cancelled/technical/uncertain siblings
never prove all-success.

Each caller request has its own durable `media_discovery_admission_outcomes` row: submitted scope,
newly admitted/existing/refused items and reasons. Shared progress cannot overwrite another
request's outcome. Convergence requires the same principal, library/Storage binding, immutable pin
and admission kind. Only an open unfrozen manifest can widen within bounds; a failed extension
reports every uncommitted/refused item, never silently drops a sibling. Another principal's owned
source yields a bounded refusal without disclosing that principal's work ID or merging into it.

Source ownership is independent of short-lived execution leases:

- Identity is Storage plus exact canonical Storage-relative path and comparable content version,
  never filename, library-relative text alone, label, principal or today's Active. Distinct canonical
  paths remain independent, including equal names under different roots.
- Reviewed fingerprints remain library-bound. Cross-binding comparisons use observed size,
  modification instant and provider-validator names; same-binding fingerprints can prove replacement.
  A proven replacement is new content. Missing/incomparable evidence is unknown and cannot release
  a live claim. Pre-change rows use only their own persisted pin/binding/progress fallback; a proven
  different canonical path never matches by a coincidental relative name.
- Queued/running/paused/four-type decision and saved-decision work keeps ownership. Settled
  `dry_run/success/skipped/cancelled/failed/ignored` items do not create perpetual history locks;
  partial/uncertain effects retain their non-replay protections. Legal continuations exclude their
  own persisted lineage, without exempting other work of the same library.
- Direct-file ownership is re-proved in the same `BEGIN IMMEDIATE` transaction as admission.
  Folder tasks precede traversal; each discovered concrete source is atomically reserved with its
  manifest/item publication. Manual, scheduled, Run once and continuation entrances share the
  ownership boundary. Storage `stat/list` I/O stays outside transactions.
- Queries restrict to the exact source before bounding owner results; recent-history windows never
  decide that a source is free. No global source catalog or unbounded history load is introduced.
- A refused source is removed by its exact Storage-relative manifest key, while the operator sees
  its library-relative path. Prune the source/observation/finding/counters together, preserving distinct
  free siblings. Control/reconcile settlement repeats that same reservation/prune decision so pause,
  cancellation or lease loss cannot restore the rejected source through a fallback publication.

`GET /api/v1/resource-libraries/{id}/files/organize-work` provides principal/library-scoped paged
history and exact `requestId` reconciliation. Prepared-work links retain their own pin/context;
generic new-organize routes guide to Files without another picker or work. Ordinary initial summary
confirmation stays in Running/All outside Attention. The center uses only the admitted organizing
population and four-type lineage described above.

Shell return context comes from the router's committed validated search, preserving bounded
filters/selection through Files and recovery without a second address-bar-derived state or allowing
credential-shaped/oversized keys. Detailed Task46.3 repair history remains at
`29a6d6d0064a5de766086446b345ae5ec2fe790f:docs/architecture.md`; it is not a second current contract.

## Automation and unattended execution

The current Automation Task Definition model is scoped to a configured ResourceLibrary and bounded
source path. Scheduler emits durable occurrences and AutomationJobs idempotently. Each Job pins the
Active snapshot at creation; the Worker runs the existing pipeline and records linked Task/TaskItem/
Result evidence.

The current implementation accepts automatic-organization only; removed Scan modes have no
compatible executor or dedicated history layer. The complete native Automation workspace below is
separately accepted by Slice43; Slice45's closure and retirement boundaries remain unchanged.

Scheduled intent is persistent and scoped to checked Enabled publication; disable/removal withdraws
it without an independent grant. The Worker rechecks live permission/definition continuity, the
admitted immutable pin, scope, capabilities and conflicts at each unperformed mutation boundary.
Completed/in-flight effects are not rolled back; uncertain mutation is never automatically replayed.

### CURRENT — Automation intent and real Run once (Slice46 PASS / CLOSED)

The ordinary V2 inventory/detail reads saved definitions and bounded `executionReadiness`, without
querying historical grant eligibility. Enabled is a published schedule state, not proof of a valid
future plan. Removed/Draft-only/unavailable states retain their actual identities; reads create no
work. Confirmed focused Save/toggle advances the same form's publication identity while preserving
later input. Peer changes retain the old candidate. Unknown responses retain principal-scoped
candidate/action/base identity and reconcile only the matching durable command and activation audit;
absence is unknown, never permission to replay. Reconnect does not resubmit commands.

All activation paths share publication intent checks. An enabled definition or deliberately saved
enabled successor requires the publisher's current `GRANT_UNATTENDED_EXECUTION` capability plus the
entry's existing configuration permissions. Activation audit stores principal, trusted-local flag and
an effective-scope digest atomically with Active. Unrelated administration changes retain the prior
intent; unreferenced Storage changes do not expand it. Effective context includes the definition,
source ResourceLibrary, strategy graph, destination libraries and referenced Storage configurations.
Legacy activation audit supplies its actual actor, never a fabricated administrator. Local CLI
publication records the invoking OS uid; `--actor` cannot impersonate remote authority. Workers
require that same trusted uid or the real configured principal's current capability.

The existing Scheduler checks current authority before normal due admission; enable itself admits
nothing. Jobs keep immutable revision/definition/scope pins. Worker/Executor checks current permission
and Enabled/presence before each remaining effect, including attachments/cleanup. Activation ancestry
also proves no intervening disable/removal: re-enabling cannot resurrect an old queued occurrence.
An enabled successor may preserve legitimately admitted work without repinning. Completed effects
and ongoing Storage calls are not rolled back. Legacy grants/revocations remain history, not gates.

Run once requires `EXECUTE_MANUAL_ORGANIZE` and an exact principal/request/observed-publication fence.
One SQLite transaction inserts its Pending organizing Task, explicit-origin Job and display context;
request uniqueness and capacity checks leave neither duplicate work nor orphan Tasks. Disabled
schedules remain runnable without changing due state. Worker consumes the pinned snapshot through
the same organizing pipeline, without an initial picker/Preview/confirmation. A previously started
Task is never rescanned after claim recovery; uncertain/completed effects require investigation.
Pending Job cancellation settles its precreated Task in the same transaction.

Before any Run once effect, configured-scope enumeration must be readable and complete within
`min(itemLimit,100)`, 10,000 visited entries, 1,000 directory reads, 2,000 pages (100 entries/page), depth 32 and 600 aggregate list-read seconds.
Unsafe/duplicate entries, invalid/repeated cursors, read failure or overflow refuse the whole prefix. These are cooperative
budgets around Storage calls, not an interrupt of an in-flight provider call. Existing real age/size
observation and one conditional wait/re-scan in `(0,60]` seconds remain; waiting consumes no read
budget. Ready siblings proceed without waiting; remaining unstable items are factual technical
failures outside four-type Attention. Healthy empty alone is no-work.

Recognition/metadata/classification/conflict blockers retain independent native Task Center recovery.
Completed linked analysis is not resolution: definition Tasks reuse the existing exact one-item
intent, source validation, summary and explicit continuation, preserving original pin and sibling
results. Job/Task linkage and explicit manual origin deduplicate runs; original attempts and recovery
progress remain distinct. Historical analysis records retain their old read/explicit-confirm semantics
and receive no automatic execute authority. Only OrganizerExecutor mutates media via Storage.

This amendment passed independent A final review with Slice46. The Slice43 accepted foundation
below remains historical where V2-AUTO-010/011 replace its normal grant and initial analysis/
confirmation sequence. Files initial confirmation is unchanged.

### CURRENT — V2 Automation workspace and consumed engine settings (Slice43 PASS / CLOSED)

Slice43 is PASS / CLOSED at implementation `97316131946bdecc483b684f6e6f6ecb98c5594d` after
whole-Slice A review from the original Base; its accepted Contract is retained at
[`e9f1a8dc:SLICE.md`](https://github.com/kentinya/mediaflow/blob/e9f1a8dc607cfc6d5ea02141b058da8ce849cd70/SLICE.md),
not the root Contract for a later Slice. The hold Contract `ed974e0df8b263f631bfe48b524da461013d8780:SLICE.md` and preservation
branch `frozen/slice-43-2026-10-15` remain unchanged. Accepted45 Scan/Preview/FileIndex removal
is an integration invariant; no exclusive retired models/repos/routes or second engine are restored.

[V2-AUTO-001–009](v2-requirements.md#automation-workspace-requirements--current-slice-43-pass--closed) describe
the accepted contract: reuse managed definitions/occurrences/grants, Scheduler/Worker/Operations and exact focused
publication, not another queue/config store. V2-AUTO-010/011 above replace independent grants
and initial manual Run once confirmation. Run once uses the same bounded pipeline and explicit
one-run command intent; min(definition ceiling,100) bounds primaries, incomplete/overflow refuses
a first-N prefix, and schedule due state/history grants do not become manual authority.
Durable origin/request/principal/pin links preserve deduplication and truthful historical metrics.

Automation execution records add a records-only `recordOutcome` envelope on the existing bounded
GET: status, noWork, confirmed primary success count and concise Chinese statement/failureReason/
nextStep. SQLite derives the original lifecycle and exact TaskItem/Result/attachment evidence without
consuming recovery lineage, changing persisted states/schema or traversing Storage. A terminal
failed/partial/cancelled original stays failed; completed work with skipped/ignored/failed/partial/
uncertain admitted work (including attachments) is failed. Fully verified success and proven empty
no-work are completed; incomplete/inconsistent proof is unknown and live/cancel-requested work stays
unfinished. Subsequent handling and restart cannot turn original failure into success.

The optional `outcome` records filter consumes this same SQL classification over the mandatory
original-Automation population, before counts, page windows and bidirectional cursors. Principal,
definition/trigger/raw-status/outcome/time/direction scope and query keys bind the actual conditions.
Raw `status` filtering, raw result/handling/handoff fields and other shared callers' default behavior,
Task Center recovery, latest outcomes and metrics remain unchanged. No client-side page filtering,
unbounded record loading, new history store or execution authority is introduced.

The UI consumes only this original-result envelope and real execution times. Its detail toggle opens
at most 执行结果和时间 / 失败原因 (failed only) / 下一步; it never renders later handling, recovery
counts/instructions, ownership, raw categories/exceptions, Task Center/definition navigation or
commands. Cancelled runs are named as cancelled, not program exceptions; uncertain effects require
inspection, never a no-effect or retry promise. Independent workspaces retain their existing recovery
entry and safe authority; a missing Task link never proves non-execution or authorizes replay.

The records API publishes one complete `failureStage` envelope across proven pre-start and formal
Task failures. A settled pre-start failure retains its durable stage/category/nextAction/statement,
with `items=[]`, all four `effects` counts zero, `itemsTruncated=false` and `unavailable=false`:
there is no formal Task or per-item effect evidence, not an unreadable history. Existing historical
rows receive this projection without migration or execution. The complete pre-start envelope no
longer causes the unchanged strict Web decoder to reject a readable mixed page. Unavailable formal
Task item evidence still reports `unavailable=true`, and actual denied/malformed/read failures remain
distinct. Records refresh uses the same bounded GET and grants no work, retry or execution authority.

Capacity bounds pending+running Jobs; stale age observes updates. Polling adoption must be proved by
fresh actual consumer values/version at safe resident-loop boundaries, independently of each Job's
media pin. API runtime binding alone is not proof of another process's cadence. Idle/long waits,
heartbeat/lease ownership and CLI/deployment overrides retain meaning; unavailable Active cannot
schedule from cache. Preserve supported history/schema/pins and non-replay; no process supervisor
or new execution parallelism. Inventory/records/Run once and the engine-settings publication and
resident adoption below are accepted parts of the same Slice.

#### Focused engine-settings publication and resident adoption

```text
GET /api/v1/operations/automation/settings   READ
  → published target (Active revision id/version/digest + the four values)
  → per-consumer adoption (each *current* resident instance's own report)
  → bounded retained stopped/stale history as diagnostics only

PUT /api/v1/operations/automation/settings   MANAGE_CONFIGURATION
  → strict four-field normalization (no other key, no bool/fractional/non-finite)
  → observed Active captured, no-op detected (publishes nothing)
  → successor Draft from that exact Active
  → only automation.{maximumActiveJobs,staleJobAgeSeconds,
                     workerPollSeconds,schedulerPollSeconds} applied
  → whole-candidate validation → runtime preparation → atomic activation

resident Worker/Scheduler loop
  → at each safe loop boundary and on each bounded recheck wake: resolve current
    managed Active → install effective cadence → only then write own report
  → configuration/heartbeat/report wakes bounded by min(cadence, 5s); the
    business claim/tick deadline is preserved across them, so a recheck never
    claims work or ticks the Scheduler early
  → an unchanged live consumer re-reports on the bounded refresh; a failed
    report write is retried and is never acknowledged as adopted
  → override (CLI/deployment) keeps precedence and is reported as an override
```

Preparation happens **before** publication: the same `before_publish` callback
every other checked Save uses constructs the successor runtime binding while the
previous Active pointer is still authoritative, so a runtime-construction fault
leaves both the persisted Active and the process binding unchanged and reports a
bounded `prepare` stage.

A Save carries a client-generated submission identity. Unknown outcomes are
reconciled against that exact submission's own durable evidence
(`committed` / `superseded` / `not_committed` / `unresolved`); equal values,
another writer's equal publication, or a still-Draft failed revision can never
certify it. A submission that terminates without ever owning a revision — a
four-field input refusal, a stale/no-op refusal, or a
persist/validate/prepare/activate fault — records its own bounded terminal
outcome under the same actor + submission identity, so a lost failure response
reconciles into a *terminal, correctable* state instead of a permanently blocked
form. A refusal decided before normalisation (for example the text `3.5` for an
integer field) can only record a bounded content fingerprint plus the rejection
code/field, because the submitted values are not valid for publication; lookup
therefore identifies that exact request *without* re-running publication
validation, while strict validation still governs every value that can actually
be published. Only terminal evidence clears the retained resubmission block,
which survives reload principal-scoped without storing a bearer token.

Recovery after a terminal non-publication, and any edit whose target moved under
a background readback, merges **per field** instead of re-arming the whole form
against a new identity. For each field it compares the baseline value the edit
started from, the operator's typed value and the value published now: an
untouched field takes the current publication (preserving another writer's
change), a changed-but-unsaved field keeps the operator's value, an already-equal
value needs no publication, and a genuine same-field overlap requires an explicit
"use current" / "keep mine" choice before Save is offered. The identity checked by
the next Save is always the latest one, so a further concurrent writer is still
fenced. The baseline values are part of the retained context; a context retained
by an older build has none and recovery then asks explicitly per differing field
rather than guessing which fields the operator edited.

Reconciliation does not rebase that editing context: the original baseline
identity/values and the unresolved conflict set survive it, so a real overlap
stays visible with both current and typed values and cannot be saved until the
operator chooses. The merged decision is bound to the exact current target read
from the reconcile answer (or an awaited successful refetch), never the
pre-request value; a failed current read leaves Save unavailable instead of
making a stale merge publishable. An explicit choice is remembered together with
the published value it reviewed, so a further change to that field reopens the
conflict rather than inheriting the old decision.

While a Save is outstanding the four inputs are read-only, so a keystroke can
never belong to a request that already left the browser. A value that still
races the response is retained and explicitly re-based onto the just-published
identity rather than being cleared or silently attached to the old one. That
comparison uses the edit snapshot the request actually started from, never the
merged candidate the request sent: the two differ by construction, so comparing
against the candidate would treat another writer's preserved field as a fresh
keystroke and restore its old value after a successful Save.

`SystemSettingsService` retains the generic Draft editor and its
`/api/v1/system/settings` semantics unchanged; the focused command is a distinct
contract, not a replacement. Shared validation stays in
`mediaflow.domain.system_settings` (now including finite-number rejection) and the
four-field subset/bounds/meanings live in `mediaflow.domain.automation_settings`.
`AutomationSettingsService` composes the existing `ManagedConfigurationService`
activation and `_document_evidence` audit rather than duplicating them.

Adoption evidence is additive durable state (`resident_settings_adoption`, runtime
schema 50) written only by the owning process *after* it installed the cadence.
Registration and heartbeat cannot write it, so an unreported consumer is reported
as unreported, and a later publication is never mistaken for an older adoption
because the row carries the publication identity it adopted. The collective claim
covers only the two resident cadence consumers; the API-local capacity/stale
basis is projected separately and never inflates a polling-adoption statement.

Current consumer membership is derived at read time from the existing
registration lifecycle and heartbeat freshness, never from a stored flag, the
newest registration only, one successful report, matching values, or a bounded
evidence page. Every registration that is live at the read timestamp is a current
consumer and must satisfy its own adoption checks — including an overridden,
unreported, incompatible-schema or older-publication instance — so one healthy
replica can never hide another's pending state. A registration that is `stopped`
or has an expired heartbeat is retained history: it stays visible as bounded
diagnostics (`historyCount` is the real total, `history` the bounded page) with a
diagnostic next action, and it can neither veto nor certify the current
population, so a fresh replacement or a recovered process restores the
collective claim without touching the predecessor row. The same instance rejoins
the current checks as soon as it heartbeats freshly again; freshness thresholds
and the registration/report rows are unchanged. Empty, stopped-only, stale-only,
unreadable-registration and unreadable-evidence reads are all explicitly
unproven rather than an empty (apparently healthy) population, and the Web
normalizer refuses a document whose collective flag contradicts its instance
evidence, whose `instanceCount` disagrees with the rows it carries, or that mixes
a live row into history.

Explicit non-goals that this delivery does not change: the admission pool is not
replaced, no new concurrency control or process supervisor is added, a poll
override is never rewritten by Web Save, and `maximumActiveJobs` remains
pending+running Jobs in the shared pool rather than worker/thread parallelism.

## API and Operator Web

The API is a versioned WSGI application over shared application/repository services. It provides
authenticated configuration, files, tasks, jobs, reviews, manual organize, recovery, automation,
schedules, notifications, logs, dashboard, security audit and system status routes. RBAC is applied
at the shared service boundary; 401/403 behavior and Web/API projections are tested together.

The embedded V1 Operator Web and the React/TypeScript V2 SPA are static UIs served by the same
Python application. V2 currently exposes Dashboard, ResourceLibrary Files, MediaLibrary, Storage,
Settings, Rules and the Operations route family for Tasks, Jobs and Organize,
Automation and Notifications. The unified Operations task center provides native task-linked
decision/recovery, cross-Task problem-type lists and supported paused-scope continuation. Cross-Task
bulk mutation and arbitrary historical Reprocess remain deferred; Advanced JSON and the general configuration
lifecycle retain their support/compatibility surfaces alongside native V2 Settings. Both UIs use the
shared `/api/v1/*` application
authority. The browser holds the API token only in memory and does not provide built-in account
login. V2 recovery hints that must survive a page reload are scoped only after a read-only API
response confirms the current principal; those hints do not grant authority or persist credentials.

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

Webhook signatures use HMAC-SHA256 over `timestamp + "." + exact UTF-8 body`. Transport/429/5xx
failures use bounded backoff; other 4xx enter dead-letter. Claims use `deliveryLeaseSeconds` (default
300); an expired claim permits another delivery attempt, with stable delivery ID for receiver
deduplication of the unavoidable at-least-once crash window. Tests pin exact configuration and send
one bounded signed request; reads expose no payload bodies or secrets.

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

## Delivery references

Accepted delivery ranges and deferrals live once in [Progress](progress.md). Fresh setup and
managed publication are described above; Storage lifecycle in [Configuration](configuration.md),
production/restart/recovery in [Deployment](deployment.md), and operator outcomes in
[Product Experience](product-experience.md). Earlier per-Slice delivery notes are reachable through
this document's historical checkpoint; they are not independent architecture states.

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

```text
ResourceLibrary ID + exact relative path
→ exact Active Storage/root → guarded live list/stat
→ explicit organize preparation → SourceIdentity + immutable plan
→ separately confirmed durable execution → Worker live-source revalidation → OrganizerExecutor
```

`RuntimeFilesBrowserService` has no FileIndex dependency or compatibility argument for physical
listing/authority. The frontend supplies library/path/cursor, not Storage paths, FileID, occurrence
or fingerprints as authority. `create_current_from_storage` derives evidence from live stat and
`create_from_sources`; execution opens the reviewed Storage/path directly, never re-resolves via
FileIndex. Index feedback/sync is removed; result/display failure cannot replay media.
The current Files page shows no recognition/organize-status feedback.

## UI-V2 direct file-management authority update — 2026-09-14

Ordinary create-folder/text, rename, Copy/Move/Delete and allowlisted text Edit use shared confined
application commands and OrganizerExecutor without media recognition/metadata/naming/planning/
Preview or raw-token ceremony. Enforce RBAC, exact library kind/Active binding, capabilities,
current entry evidence, path/selection/entry/depth/projection limits and explicit Delete/Replace/Save
intent. Cross-kind direct transfer, Upload/Download, arbitrary binary/media editing, unbounded/root
delete and host-path access remain outside scope.

Same-Storage operations need advertised native capability, no silent fallback. Cross-Storage Move
is explicit Copy→destination digest verification→Delete-source; failed verification preserves the
source, known partial effects retain both-copy diagnosis and uncertain effects require investigation.
Long/batch work uses durable per-item Tasks/checkpoints; live listing stays authoritative after work.
Rename/Delete use metadata-only evidence with optional provider fingerprint: once observed it remains
binding. Text Edit separately binds loaded content digest and is capped at 512 KiB.
Result/display failure never admits/replays a command. The durable Delete/fencing detail follows.

## CURRENT — Slice 44 RO-1 metadata fences and durable Delete

Rename and confirmed Delete bind the exact library kind/ID, Storage/root, relative path and
immutable configuration snapshot to server-observed type, size and modification time; the
provider fingerprint is optional. When observed, a fingerprint remains binding and cannot vanish
or change. Evidence and confirmation reads use metadata only and never read selected file bytes or
run FULL Hash. This permits SMB/OpenList-like providers to support these operations while
acknowledging indistinguishable replacement and external check-to-write windows as limits of the
available provider observations.

Both library pages preserve exact long names/whitespace in list/grid navigation, provide full-name
hover/focus disclosure and bounded breadcrumb scrolling, and reflow controls below long paths
without overlapping entries. Display truncation never rewrites path authority.

Long and batch Delete persists the exact flattened confirmed scope, one TaskItem per entry and its
effect certainty in the existing `files_transfers` claim/lease/mutation-fence table. The resident
Files Worker reconstructs the pinned kind and immutable revision, removes children before
directories, and invokes mutation only through `OrganizerExecutor`. The existing Task pause,
cancel and safe-continuation controls are available through the originating library's local status
readback; an uncertain delete is read back and recorded for investigation, never replayed. Existing transfer rows without a
`direct_delete` authority discriminator remain Copy/Move work and keep their historical format.

The native Delete pages create a request ID before submitting and retain only that ID, the exact
confirmed paths and scope digest in principal-scoped session storage. The backend binds the ID to
the exact library kind/ID, scope, and immutable configuration pin, and uses it as the durable Task
identity. Reusing the same ID and binding reads back the existing Task; reusing it with a different
binding is rejected. After an unknown HTTP response, each page reads that Task before offering an
explicit repeat with the same ID and unchanged scope. Duplicate paths and selected descendants are
collapsed to the same canonical top-level Delete scope for impact and admission. Known item-level
refusals persist bounded categories through TaskItem, Result and status projections; the pages map
those categories to recovery guidance without exposing adapter exception text.

## UI-V2 Files and shared-shell contract update — 2026-09-14

The shared light AppShell and Files hierarchy use [the Files visual specification](file-page-visual-spec.md).
The supplied image is immutable reference input; samples are not runtime authority. Exact entry/path
identity, responsive/keyboard navigation and bounded actionable states apply to both library kinds;
page-specific commands remain behind the shared Python authority.


## Slice 37 delivery — 2026-09-22

See [Progress](progress.md) for accepted Base/Head and deferrals; closure did not grant unrelated
business scope or automatic uncertain replay.
