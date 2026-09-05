# MediaFlow Configuration Architecture and Operator Guide

This document describes the configuration behavior implemented by the current repository. It is an
operator guide, not a Phase or Task log. Large-Slice status is maintained in
[`roadmap.md`](roadmap.md), [`progress.md`](progress.md) and [`SLICE.md`](../SLICE.md).

## Configuration authority

MediaFlow has two deliberately different configuration entry paths:

1. **JSON bootstrap** is the compatibility path used before the first managed Active revision. The
   full JSON document supplies runtime Storage, library, policy, Metadata, API and operational
   settings. `MEDIAFLOW_CONFIG` selects this document.
2. **Managed Configuration** is the runtime authority after an operator explicitly activates a
   revision. The active revision is an immutable, digest-identified snapshot persisted in SQLite.
   Runtime requests and queued work use that snapshot; JSON is not a fallback source.

The bootstrap loader also has a minimal management boundary containing only the SQLite database
locator and environment-owned API-principal references. That boundary keeps authenticated
configuration status and recovery available when the managed Active revision is missing, corrupt,
schema-incompatible or otherwise not runtime-consumable. It does not provide workflow defaults.

The current fresh-instance path supports a minimal management-only bootstrap containing only the
database locator and environment-owned API-principal references. An authenticated operator can
create the first complete managed Draft through Web/API without supplying workflow defaults or a
complete runtime JSON document. The compatibility JSON bootstrap remains supported for legacy,
migration and compatibility operation; it is not a competing Active source after managed activation.

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

Runtime validation requires the complete configured catalog graph, including
`recognitionRules`, `recognitionTypePolicies`, `metadataPolicies`, `namingPolicies`,
`classificationPolicies`, and `organizePolicies`. Production loading does not fill missing sections
from an A/B/C default. `config/strategy.example.json` is the canonical example; development and
smoke constructors are test fixtures.

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
validation/test evidence. Editing an Active or Superseded revision is refused; import a new Draft.
Activation is atomic. A failed activation leaves the previous Active revision and the candidate Draft
intact. A missing or invalid Active revision fails media work closed while status and replacement
Draft recovery remain available through the bootstrap database locator.

CLI equivalents are:

```bash
mediaflow config status
mediaflow config draft-import
mediaflow config draft-validate REVISION_ID
mediaflow config activate REVISION_ID --expected-version VERSION
```

The authenticated Web Configuration view exposes the same operations through the API. JSON import
creates a Draft; it never silently changes Active.

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

The canonical managed document and object service preserve references and optimistic edits for:

- Storage definitions;
- ResourceLibrary and MediaLibrary definitions;
- RecognitionType, RecognitionRule and RecognitionTypePolicy mappings;
- MetadataPolicy, including the configured TMDB Provider reference;
- NamingPolicy, ClassificationPolicy and OrganizePolicy;
- Automation Task Definitions.

The object service rejects unknown fields, validates IDs and references, records bounded redacted
audits, and blocks deletion while an object is referenced. A valid unreferenced object can be deleted;
the reference check is not a blanket refusal of all deletion. Any edit is applied to the Draft and
returns that revision to `Draft`.

The current Web guided forms cover Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic
S3-compatible Storage, ResourceLibrary, MediaLibrary and the policy graph needed by the first-runtime
journey. The raw whole-document JSON editor remains available as a compatibility path for
configuration families without a guided form.
Remote Storage definitions and their deployment-owned secret references remain editable in Drafts;
redaction applies to read projections and evidence, while actual secret values are never persisted or
exposed.
The current top-level Configuration page leads with whole-document JSON staging. Guided controls are
available only after opening a revision; several policy families still use bounded JSON-object
editors, copy/enable/disable actions are not presented consistently across families, and the existing
successor-Draft action is labelled `Import current JSON as Draft` rather than a natural
`Edit Active by creating Draft` flow. These are Web/IA limitations, not permission to make Active
mutable.

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
editor does not probe or mutate a Storage while saving a Draft.

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
- the older Local setup check as a bounded Local diagnostic.

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
exception for Provider access, but it still starts no media work and performs no Storage mutation.

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

Current authenticated Web/API surfaces share application services, permission checks and recovery
semantics. They include:

- Configuration status, revision detail, whole-document Draft import/edit/validate/activate and
  guided object editing;
- exact-revision Strategy Test, Metadata candidate/correction, Naming, Classification, Organize
  authority, destination preview, per-Storage read-only checks, Local diagnostic and
  provider-neutral destination precheck;
- Dashboard, Files list/detail/stats, Task/TaskItem and Job observability;
- Recognition, Metadata, Classification and conflict review actions;
- bounded manual Preview and reviewed one-shot manual execution;
- processing checkpoint recovery and bounded batch recovery;
- real configured Storage Files, separate FileIndex/current-source lifecycle and disposition,
  bounded manual Scan and explicit Reprocess admission;
- conflict/review/recovery continuation with independent per-item outcomes;
- Processing Worker registration/readiness, heartbeat, ownership and claim-fencing evidence;
- Automation Task Definition validation/Preview, persistent scoped grant/revoke, occurrences and
  per-item outcome/recovery;
- schedules, notification deliveries, security audit and redacted operational logs.

The current UI has a read-only System status view. It reports bounded runtime/configuration status
and wiring; it does not consume or edit a System Settings object. Webhook delivery exists as an
engine and read-only operations view, but Web/API Webhook configuration, test and dead-letter
management are Slice 28 work.

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
mediaflow scan --limit 20
mediaflow preview --limit 20
mediaflow organize --limit 20
mediaflow organize --execute --limit 20
```

`scan`, parsing, recognition, metadata lookup, naming, classification, planning and Preview do not
mutate media. Only an explicit execute boundary can reach `OrganizerExecutor`, and conflict,
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

The implementation currently declares:

- runtime SQLite schema: `33` in `mediaflow/infrastructure/sqlite_runtime.py`;
- configuration-management SQLite schema: `10` in
  `mediaflow/infrastructure/sqlite_configuration_management.py`;
- managed configuration document schema: `1` in
  `mediaflow/application/configuration_snapshot.py`.

These numbers are compatibility facts, not feature-phase labels. Runtime and configuration
repositories refuse a newer unsupported schema and run their additive initialization/migration
logic for older databases. Do not infer a product capability from a historical migration marker.

## Current limitations and remaining V1 work

Slices 26 and 27 are `PASS / CLOSED`. The remaining V1 order is:

| Status | Capability |
|---|---|
| Slice 28 PLANNED | Day-2 forms-first configuration/object lifecycle, consumed System Settings, versioned secret-free configuration/result import-export, and managed Webhook configuration/test/delivery recovery |
| Slice 29 PLANNED | Docker Compose production release, production WSGI server, `/data` durability, non-root mounts, health, restart persistence and fail-closed upgrade/migration |
| V1.x/V2 | Provider switching and additional production Providers, built-in user/session identity, OIDC, general Secret Store and broader recovery such as automatic uncertain-mutation replay or historical rollback |

Arbitrary host-path access and mutation-based capability probes are not current capabilities. The
setup Storage Browser, read-only setup checks and provider-neutral destination precheck remain bounded
first-setup evidence; the runtime Files browser and Slice 27 manual operations are separate current
operator surfaces. The current `wsgiref.simple_server` listener is a development / trusted-loopback
boundary, not production HTTP serving.
