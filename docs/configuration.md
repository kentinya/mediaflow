# MediaFlow Configuration Architecture and Operator Guide

This document describes the configuration behavior implemented by the current repository. It is an
operator guide, not a Phase or Task log. Large-Slice status is maintained in
[`roadmap.md`](roadmap.md), [`progress.md`](progress.md) and [`SLICE.md`](../SLICE.md).

## Configuration authority

| Path | Authority |
|---|---|
| JSON bootstrap (`MEDIAFLOW_CONFIG`) | Compatibility runtime input before managed activation; also supports legacy/exchange/recovery use. |
| Managed Configuration | Explicitly activated immutable SQLite revision/digest; sole runtime authority after activation, with no JSON/Draft/stale-cache fallback. |
| Minimal management bootstrap | Deployment-owned database locator and API-principal environment references keep status/setup/recovery available without business Active or workflow defaults. |

A fresh operator creates/resumes the first Draft in Web Settings and may activate a valid empty
business baseline. Populated objects/references still validate; missing capability and corrupt
prior Active are distinct states. See [the setup journey](product-experience.md#first-time-setup).

## Bootstrap configuration

The compatibility document contains at least:

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
  "historyPath": ".mediaflow/history.jsonl",
  "persistence": {"databasePath": ".mediaflow/mediaflow.sqlite3"}
}
```

For populated organizing capabilities, declare their actual recognition/type-policy/Metadata/
Naming/Classification/Organize references; dangling objects fail validation. Unrelated empty families
are legal and create no capability/defaults. `config/strategy.example.json` is the complete working
example; A/B/C development/smoke constructors are test fixtures, never production fallback.

Validate without scanning, contacting a Metadata Provider or mutating Storage:

```bash
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
mediaflow config validate
mediaflow storage list
mediaflow storage check [STORAGE_ID]
```

Credentials are never placed in this JSON. Storage passwords/tokens/access keys and TMDB credentials
are referenced by environment-variable names and resolved only at the infrastructure boundary.

## Managed lifecycle

Managed revisions have four persisted states:

| State | Meaning |
|---|---|
| `Draft` | Editable candidate. It is not consumed by runtime. |
| `Validated` | One exact draft version passed the canonical runtime loader and reference validation. It is still not active. |
| `Active` | Explicitly activated immutable snapshot consumed by the runtime. |
| `Superseded` | Former Active revision retained for history and pinned-work inspection. |

The lifecycle is:

```text
Draft → Validate → Validated → explicit Activate → Active runtime snapshot
```

Editing a Draft increments its optimistic version, recalculates its digest and invalidates prior
validation/test evidence. Active and Superseded revisions remain immutable. Editing the current
Active explicitly creates a successor Draft seeded from that exact snapshot; Advanced JSON or package
import can also create an inactive Draft for compatibility, exchange or recovery. Activation is
atomic. A failed activation leaves the previous Active revision and the candidate Draft intact. A
missing or invalid Active revision fails media work closed while status and replacement Draft
recovery remain available through the bootstrap database locator.

### Files-page ResourceLibrary save

`+ 添加资源库` submits one complete candidate. The backend merges exact current Active, validates
references/applicable read-only evidence and atomically publishes runtime. No separate ordinary
Validate/Activate clicks. Invalid/duplicate/stale fields, failed evidence or runtime publication
preserve prior Active and correctable input; a failed command cannot display a saved library.

### Current page-local library editing

ResourceLibrary/MediaLibrary card Edit loads exact Active, keeps ID immutable, edits name/enabled/
Storage/kind-relative root and preserves hidden fields. Save uses optimistic concurrency, whole
validation, applicable evidence and atomic binding. It changes configuration only, never creates/
migrates/moves/deletes media; admitted work keeps its old pin. Removal is reference-safe and media-free.

The general configuration CLI still exposes explicit lifecycle operations:

```bash
mediaflow config status
mediaflow config draft-import
mediaflow config draft-validate REVISION_ID
mediaflow config activate REVISION_ID --expected-version VERSION
```

Web's general forms-first successor flow and Advanced JSON/import/export share these services.
Imported packages/JSON are inactive Drafts, never implicit Active replacements.

## Immutable runtime snapshot

The runtime binding records the Active revision ID, version and SHA-256 digest. Every new Job and
every scheduled occurrence records the snapshot identity it consumes. Queued or running work does
not change behavior merely because a later revision becomes Active. API request handling refreshes
the binding from the current Active revision and fails closed if integrity, schema or runtime
loading cannot be proven.

The UI's Active identity is derived from the same managed revision used to build the runtime binding.
It must not display a Draft, an arbitrary database row or a stale process snapshot as Active. A
checked activation publishes no scan, Job, Task, Automation occurrence or media mutation; a later
explicit Preview or execution request is required.

## Current managed object families

Storage; ResourceLibrary/MediaLibrary; RecognitionType/Rule/TypePolicy; MetadataPolicy (TMDB reference);
Naming/Classification/Organize policies; Automation definitions; Webhooks/events. Applicable
create/copy/edit/enable/disable/reference-safe delete uses bounded redacted audit, strict IDs/fields,
optimistic versions and dependency impact. Referenced deletion fails; valid unreferenced deletion
is not blanket-refused. Generic edits return a Draft; focused page commands may compose activation.

Typed forms cover every supported Storage kind and object family; bounded nested JSON and whole-
document Advanced exchange remain support surfaces. Secrets stay environment references. System
Settings distinguishes actual runtime Active/consumption from editable successor and deployment/
restart-only values; another snapshot's values cannot be labelled consumed.

## Native V2 organizing-rules management

`/ui-v2/rules` reads Overview and seven family inventories from exact Active without creating Drafts.
Add/Copy explicitly opens a candidate; Edit is a full-page route with immutable ID. One checked Save
publishes the focused successor, preserving unrelated Drafts/hidden configuration, prior Active on
known failure and correctable input. Unknown publication is read back before another submission.
Failed reference-impact evidence blocks removal; navigation/tests do not publish.

Family-local tests validate only the exact non-Active object and necessary inputs/references using
production engines. Overview separately checks the full flow. Offline tests call no Provider/media
Storage, explicit live Metadata uses the configured Provider, and neither grants execution or
publication. [Product Experience](product-experience.md#object-scoped-tests-and-complete-flow-checks)
defines each test's input/result/recovery; C remains C under A policy reuse. Save still checks the
whole successor and applicable evidence, not merely local success.

New Classification uses MediaLibrary ID plus safe path without a name/ID prefix; labelled legacy
`library/path` remains until explicit impact-acknowledged checked conversion. Preserve its path and
all historical pin semantics. Scanner/manual discovery consume the same pinned filters/depth and
real elapsed stability policy. Forms retain tab-scoped correctable values, never credentials or
runtime authority. Empty/partial graphs explain missing dependencies without generating policies.

## Storage configuration model

The runtime loader supports these Storage types:

| Type | Current implementation | Current managed Web setup |
|---|---|---|
| Local | Runtime adapter and JSON loading | Guided form and read-only setup checks |
| SMB | Runtime adapter and JSON loading | Guided form, secret reference and read-only setup check |
| OpenList | Runtime adapter and JSON loading | Guided form, secret reference and read-only setup check |
| AWS S3 | Runtime adapter and JSON loading | Guided form, secret references and read-only setup check |
| Cloudflare R2 | Runtime adapter and JSON loading | Guided form, secret references and read-only setup check |
| Generic S3-compatible | Runtime adapter and JSON loading | Guided form, secret references and read-only setup check |

Adapters implement the Storage port and report capabilities. Unsupported Move, Copy, Delete,
HardLink or SoftLink operations fail explicitly; there is no implicit fallback. The managed object
editor does not probe or mutate a Storage while saving a Draft. The Files-page ResourceLibrary
save is the explicit page-local exception: it runs the existing bounded checks and activation
workflow as one backend command, and it still does not mutate media Storage.

## Path model

Paths have different meanings at each boundary:

- `Storage.rootPath` is owned by the adapter. Local uses a host-visible absolute root; OpenList uses
  its configured logical service root; SMB and S3/R2 use their adapter-specific root semantics.
- `ResourceLibrary.storagePath` is a normalized path relative to its Storage root and is the path
  used for configured discovery.
- `ResourceLibrary.displayRootPath` is optional display/association evidence for an explicitly
  supplied local path. It does not replace `storagePath` during no-path scanning.
- `MediaLibrary.rootPath` is a normalized destination path relative to its Storage root.

Plans and evidence retain Storage identity plus Storage-relative paths. A host mount path is not
embedded into a remote Storage logical path. Local adapter confinement rejects absolute or escaping
logical paths and resolves existing links before access.

### OpenList service root and Web recovery

For OpenList, an empty `rootPath` or `/` denotes the provider's service root. It is not a Local host
root. The Storage workspace must display this as a provider root and preserve it through Save,
inventory, detail and Edit. Local and other provider path validators retain their own rules.

The V2 Storage workspace accepts and displays both values through Save, Active inventory, detail and
Edit, including entries saved before this correction. A failed list read remains a read/presentation
failure and does not imply that Save rolled back; verify current Active state before any explicit
new submission. For genuine setup-required state, the Storage page offers the existing V1
Configuration first-setup handoff and returns to refreshed Storage truth. No direct database edit,
configuration reset or physical-file migration is required.

## Validation and evidence

Validation uses the same normalized runtime loader that constructs production policy and Storage
configuration. It is structural/reference validation and does not scan, contact a Provider or call
mutating Storage methods.

The current exact-revision evidence paths are:

- Recognition Strategy Test, offline by default and live only on an explicit action;
- MetadataPolicy offline/live testing and bounded candidate selection/correction through TMDB;
- Naming preview;
- Classification preview;
- Organize authority explanation;
- Composed destination preview;
- provider-neutral per-Storage read-only setup checks;
- provider-neutral destination precheck;
- the older Local setup check as a bounded Local diagnostic;
- managed Webhook endpoint testing bound to the exact revision/version/digest.

Evidence is bounded, secret-free and tied to exact revision ID/version/digest. It records outcome,
failure category, side-effect statement, retry safety and next action where applicable. Stale,
missing or failed evidence cannot silently authorize checked activation.

### Read-only checks and previews

Naming, Classification, Organize authority and composed destination preview construct no Storage,
Provider, Planner, Executor, Task or Job. They calculate or explain behavior only. Per-Storage setup
checks and the provider-neutral destination precheck construct a read-only Storage view and use
bounded read-only operations such as `List`/`Exists`/`Stat`; they do not create directories, write
files, move, copy, delete, scan recursively or grant execute authority. The older Local setup check
remains a Local diagnostic with the same read-only boundary. Live Strategy Test is the deliberate
exception for Provider access, and an explicit Webhook test sends one bounded signed request to the
configured endpoint. Neither starts media work, creates an Outbox delivery nor performs Storage
mutation.

### Checked activation

The guided checked path requires current evidence for the exact revision:

1. the Draft is successfully validated;
2. the applicable Recognition Strategy Test is complete;
3. every applicable enabled Storage referenced by a ResourceLibrary or MediaLibrary has passed its
   current provider-neutral read-only Storage check; and
4. when a MediaLibrary destination is declared, the current provider-neutral destination precheck
   is successful.

The server rechecks revision identity, evidence identity and dependency validity in the activation
transaction. Compatibility activation is a distinct, explicitly labelled path; it is not evidence
that the guided safety checks passed.

## Web, API and CLI surfaces

Authenticated surfaces share application behavior/RBAC/audit: exact Active/successor lifecycle,
objects/reference impact, versioned secret-free configuration/result exchange, Settings and Rules,
bounded tests/checks/Preview, library Save, live Files/maintenance, Task/Job/results, review/recovery,
Worker readiness, Automation/grants/occurrences and Webhook delivery recovery.
[Product Experience](product-experience.md) owns complete ordinary journeys; [Architecture](architecture.md)
owns execution and [Deployment](deployment.md) runtime administration. Configuration reads/tests/
publication create no media work. Notification retry/requeue changes only that delivery, not media.
FileIndex still has separate pending-retirement dependencies; it is never live Files authority.

## Secret boundary

Normal configuration stores secret references such as `tokenEnv`, `passwordEnv` or `secretEnv`, not
secret values. Resolved values are read from the process environment only at the adapter or
authentication boundary. Redaction applies to configuration projections, audits, evidence, results,
logs, errors and Web responses. Authorization headers, cookies, tokens, passwords, API keys and
private endpoint credentials must not appear in SQLite evidence, Git, fixtures or test output.

The current system does not provide a general Secret Store, automatic secret rotation, Docker
Secrets-specific ingestion, built-in username/password login or OIDC. Those are V1.x/V2 or explicit
deployment responsibilities.

## Runtime behavior and operational commands

The production CLI workflow remains explicit and DryRun-first:

```bash
mediaflow config validate
mediaflow preview --limit 20
mediaflow organize --limit 20
mediaflow organize --execute --limit 20
```

Parsing, recognition, metadata lookup, naming, classification, planning and Preview do not mutate
media. Only an explicit execute boundary can reach `OrganizerExecutor`, and conflict,
capability, overwrite and deletion rules remain in force.

Configuration edits, validation, test evidence and activation do not start a scan or execute media
work. Runtime database persistence, backups, restore and migration are separate operational
boundaries documented in [`release.md`](release.md).

`storage list` prints configured definitions and declared capabilities without constructing or
connecting an adapter. `storage check` performs a bounded read-only preflight for each selected
Storage, isolates failures per Storage and never creates directories, writes, moves, copies or
deletes media. A successful preflight is evidence of that read-only check only; it is not an execute
authority and does not replace checked activation evidence.

## Schema and compatibility markers

Compatibility versions are declared in `mediaflow/infrastructure/sqlite_runtime.py`,
`mediaflow/infrastructure/sqlite_configuration_management.py` and
`mediaflow/application/configuration_snapshot.py`. These are compatibility markers, not feature
statuses. Repositories reject newer unsupported schemas; supported upgrades/restore follow the
explicit [deployment maintenance procedure](deployment.md#backup-upgrade-and-migration-recovery).
Do not infer a feature or permission to rebuild user data from an old schema number.

## Current limitations and post-V1 / V2 boundaries

Provider switching/new Providers, built-in users/sessions/OIDC, general Secret Store/Docker Secrets,
automatic uncertain replay and historical rollback remain outside the accepted baseline. No arbitrary
host paths or mutation-based capability probes. Native Settings and Rules are delivered; that does
not imply V1 cutover, the remaining frozen Automation workspace or active45 completion.
Production uses Waitress `api serve-production`; standard-library `api serve` stays trusted-loopback.
See [Roadmap](roadmap.md), [Progress](progress.md) and [Deployment](deployment.md) for their own facts.

### Operational setting meanings

| Setting | Implemented meaning |
|---|---|
| `workflowRetry` | `enabled` defaults false; `baseDelaySeconds`/`maxDelaySeconds` bound backoff. Read-only retry covers normalized timeout/connection/rate-limit/temporary-provider failures before planning/execution. `maxAttempts` 1–10, `maxDelaySeconds` ≤300, `jitterRatio` 0–1; never retries mutation/uncertain effects or grants execute authority. |
| `automation.maximumActiveJobs` | Default 100; atomic shared Pending+Running backlog bound, not worker parallelism. Terminal Jobs release capacity. |
| `automation.staleJobAgeSeconds` | Default 3600, range 60–604800; no-update diagnostic, not total-runtime timeout or death/replay authority. Stale lists are bounded 100; inspect Worker and effects before permitted explicit recovery. |
| Preview Cron schedules | Validated five numeric fields with IANA timezone; `*`, lists, inclusive ranges and positive steps, no seconds/names/macros/shell/catch-up backlog. Missing DST wall times skip; ambiguous wall time fires once. Definitions/scheduled organizing use their separate explicit grant boundary. |
| Organize Hash/attachments | Hash defaults NONE with zero reads; FAST is bounded prefix evidence, FULL is bounded streaming. Failed/unknown comparison adds a conflict and never authorizes overwrite/delete. Opt-in attachments are matched only in the primary directory; unknown files are not included/cleaned. |
| Source cleanup / rollback | Cleanup defaults none; only fully verified successful MOVE may clean bounded ancestors below the exclusive ResourceLibrary root. `rollback.enabled` defaults false, `cleanupCreatedDirectories` true; compensation covers only this invocation's verified effects, never changed targets, reappeared sources or older executions. Complete policy constraints remain in Requirements. |
