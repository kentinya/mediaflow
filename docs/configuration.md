# MediaFlow Configuration Architecture and Operator Guide

This document describes the configuration behavior implemented by the current repository. It is an
operator guide, not a Phase or Task log. Large-Slice status is maintained in
[`roadmap.md`](roadmap.md), [`progress.md`](progress.md) and [`SLICE.md`](../SLICE.md).

## Configuration authority

| Path | Authority |
|---|---|
| Managed Configuration | Explicitly published immutable SQLite revision/digest; sole runtime authority after publication, with no JSON/draft/stale-cache fallback. |
| Minimal management bootstrap (`MEDIAFLOW_CONFIG`) | Deployment-owned database locator keeps status/setup/recovery available without business Active or workflow defaults; accounts live in the database. |

A fresh operator explicitly initializes an empty managed configuration in Web Settings and may
publish a valid empty business baseline. Populated objects/references still validate; missing capability and corrupt
prior Active are distinct states. See [the setup journey](product-experience.md#first-time-setup).

## Bootstrap configuration

A fresh deployment starts from the minimal management bootstrap:

```json
{
  "version": 1,
  "persistence": {"databasePath": "/data/mediaflow.sqlite3"}
}
```

The bootstrap contains no credential or account identity. Create the first administrator with a
host-issued one-time code (`mediaflow accounts issue-setup-code`) from the Web sign-in page.

It declares no Storage, ResourceLibrary, MediaLibrary, rule, policy or Webhook, so a fresh
installation can start all services, expose status/recovery and initialize an empty configuration
before any business object exists. Generate the same shape with
`python3 scripts/make_deployment_config.py --output config/mediaflow.json`; add
`--database-path PATH` only when the durable locator differs from `/data/mediaflow.sqlite3`.

`config/strategy.example.json` is the complete canonical business example. It is **not** a startup
bootstrap: its example paths and deployment identity are not portable. Render its portable managed
input, edit its Local Storage roots and library paths for the target deployment, and import that
as a checked publication:

```bash
python3 scripts/make_deployment_config.py \
  --output config/mediaflow.json \
  --database-path "$PWD/.mediaflow/mediaflow.sqlite3" \
  --configuration-output config/mediaflow.activation.json
mediaflow --config config/mediaflow.json config publish \
  --file config/mediaflow.activation.json
```

The bootstrap named by `--config` (or by an exported `MEDIAFLOW_CONFIG`) supplies the deployment
locator and authority for publication; without one the command refuses to run. The block uses the
host-local durable locator so this command and the service opened later share one database; in the
container layout omit `--database-path` and keep the default `/data/mediaflow.sqlite3`.

The generated input omits the database locator and any retired API identity, so import binds the
receiving deployment's own authority. Unrelated empty families are legal and create no
capability/defaults; populated references that point at missing objects fail validation.

The command validates the candidate, binds deployment authority and publishes atomically. It runs
the same applicable read-only checks as the Web form: read-only checks for every referenced enabled
Storage, the offline recognition strategy test, and the destination precheck. A failed check leaves
the previous Active and the submitted input intact and names the correction. A typical recoverable
first-setup case: while the target directory does not exist yet, the destination precheck fails —
with `暂不可用` while the destination Storage root itself is not created or mounted, and with
`目标库根路径不存在` once that root is reachable but the MediaLibrary root is still missing.
Create the directories the candidate names or repair the corresponding mount, then apply again.
After publication the page reports the new Active revision, version and digest.

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

Managed persistence contains current and historical published snapshots only:

| State | Meaning |
|---|---|
| `Active` | Explicitly published immutable snapshot consumed by the runtime. |
| `Superseded` | Former Active revision retained for history and pinned-work inspection. |

One apply command composes a candidate from the current Active, increments its optimistic edit
version, recalculates its digest, revalidates references and runs applicable evidence, then
publishes atomically. The in-memory candidate and its read-only evidence exist only for that command
and are discarded on refusal; no Draft or validated revision row is written. Active and Superseded
revisions remain immutable. A
missing or invalid Active revision fails media work closed while status and explicit full-replacement
recovery remain available through the bootstrap database locator.

### Files-page ResourceLibrary save

`+ 添加资源库` submits one complete candidate. The backend merges exact current Active, validates
references/applicable read-only evidence and atomically publishes runtime. No separate draft
lifecycle clicks. Invalid/duplicate/stale fields, failed evidence or runtime publication preserve
prior Active and correctable input; a failed command cannot display a saved library.

### Current page-local library editing

ResourceLibrary/MediaLibrary card Edit loads exact Active, keeps ID immutable, edits name/enabled/
Storage/kind-relative root and preserves hidden fields. Save uses optimistic concurrency, whole
validation, applicable evidence and atomic binding. It changes configuration only, never creates/
migrates/moves/deletes media; admitted work keeps its old pin. Removal is reference-safe and media-free.

The general configuration CLI exposes direct publication:

```bash
mediaflow config status
mediaflow config initialize
mediaflow config publish --file config/mediaflow.activation.json
mediaflow config publish --file config/mediaflow.activation.json --replace-active
mediaflow config retire-unpublished
mediaflow config retire-unpublished --confirm
```

Each command selects the deployment bootstrap with `--config PATH` or `MEDIAFLOW_CONFIG`; the
example above relies on the `export` in the preceding section. `config initialize` publishes an
empty Active only when managed activation has never existed. `config publish` runs the same
applicable read-only checks as the Web form and publishes the supplied document. If a published
Active revision is missing or corrupt, `--replace-active` is the explicit recovery command; it
requires `--file` and never infers a replacement from retained history. The optional `--actor`
labels the audit record for `initialize` and `publish`. The retired `draft-import`,
`draft-validate` and `activate` commands, aliases and parameters are unknown command-line inputs.

### Previous-store data switch

A store that still reports configuration schema 11 may contain unpublished revisions and their
draft-only evidence from the retired draft lifecycle. This build does not retire them while opening
the database. `config status` reads that file through a read-only connection and reports
`DATA_SWITCH_REQUIRED` with the exact affected revision IDs, evidence per revision, affected audit
rows and any admitted Task that pins one of them. Web/API startup and `config initialize`/`config
publish` refuse to open the store, naming the same affected revision IDs, until the switch is applied.

Review the reported scope, then apply it explicitly. Without `--confirm` the command only prints
the same scope and changes nothing:

```bash
mediaflow --config config/mediaflow.json config status
mediaflow --config config/mediaflow.json config retire-unpublished --confirm
```

One transaction removes only the listed unpublished revisions, their revision-bound evidence and
their lifecycle audits, then advances the configuration marker to 12. Published Active and
Superseded revisions keep their IDs, digests, audits, Task pins and results. A Task pin to an
affected revision blocks the switch and is named with its Task ID; an SQLite failure rolls the
transaction back and leaves the previous store intact. Start or restart the services after a
successful switch.

Web settings, business forms and `系统设置` → `高级配置` → `导入配置` share the same direct
publication services. The import entry accepts either the complete configuration JSON or a
previously exported redacted configuration package, checks it against the current Active baseline
and publishes only after the operator selects `核对并应用`. Package import requires both
configuration-management and activation permission, exactly like complete JSON publication. The
read-only `配置 JSON` and `脱敏配置包` views remain available on demand. Imported packages/JSON are
validated and published; they never create an inactive draft.

## Immutable runtime snapshot

The runtime binding records the Active revision ID, version and SHA-256 digest. Every new Task and
every scheduled occurrence records the snapshot identity it consumes. Queued or running work does
not change behavior merely because a later revision becomes Active. API request handling refreshes
the binding from the current Active revision and fails closed if integrity, schema or runtime
loading cannot be proven.

The UI's Active identity is derived from the same managed revision used to build the runtime binding.
It must not display a draft, an arbitrary database row or a stale process snapshot as Active. A
checked publication starts no Task or Automation occurrence or media mutation; a later explicit
organizing analysis or execution request is required.

## Current managed object families

Storage; ResourceLibrary/MediaLibrary; RecognitionType/Rule/TypePolicy; MetadataPolicy (TMDB reference);
Naming/Classification/Organize policies; Automation definitions; Webhooks/events. Applicable
create/copy/edit/enable/disable/reference-safe delete uses bounded redacted audit, strict IDs/fields,
optimistic versions and dependency impact. Referenced deletion fails; valid unreferenced deletion
is not blanket-refused. Generic edits validate and publish a checked successor; focused page
commands use the same boundary.

Typed forms cover every supported Storage kind and object family; bounded nested JSON and whole-
document Advanced exchange remain support surfaces. Secrets stay environment references. System
Settings distinguishes actual runtime Active/consumption from submitted input and deployment/
restart-only values; another snapshot's values cannot be labelled consumed.

## System Settings Web

Open `系统设置` (`/configuration`) from the sidebar or a business page's setup/recovery
link. The page starts with a compact configuration summary and the three system runtime settings.
Published values and actual process adoption remain separate; instance details can be expanded.
Command readiness, rule-family counts, exact snapshot identities and consumption evidence are in
the secondary `诊断` section rather than repeated in the main settings view.

Settings reads the latest published values on entry, tab return, reconnect and after application.
It updates untouched fields and keeps edits in progress. A field changed by another operator is
marked for review.

The two save paths use the same direct publication rule:

- `系统运行设置` → `应用更改` publishes only the changed runtime fields through the focused checked
  command. No draft or separate activation clicks are required.
- `高级配置` groups the wider allowlisted fields into `语言与时区`, `路径`, `日志`, `重试`
  and `通知运行`. `应用更改` publishes only that group's changed fields; other groups'
  unsaved input stays in the form. `放弃本组修改` affects only that group. Booleans use explicit
  choices, numbers are validated without truncation or blank-to-zero conversion, and each group
  shows whether the new value takes effect immediately or requires a restart.

The backend binds the exact Active baseline and runs applicable checks in place. A failed check or
stale baseline keeps the previous Active and the correctable input; there is no saved draft to
resume. A valid empty baseline has no applicable checks to run.

`配置内容` is closed by default. The exact Active JSON and the separately generated redacted
package identify their source and open on demand. Reads and exports do not publish configuration.
An unknown write is verified automatically by the same request identity; the page keeps the
application result and the current effective values distinct and never automatically replays the
publish. Leaving unsaved input requires an explicit decision. A setup/recovery return goes back to
the allowlisted source page and reads its current state.

## Native V2 organizing-rules management

`/rules` reads Overview and seven family inventories from exact Active without creating drafts.
Entering, returning to the page or reconnecting reads current configuration automatically; the
family, keyword, state filter and unsaved input are preserved. Overview has no inventory search; each family has one local
search and its existing state filter. Changing family clears the keyword. Overview keeps real counts,
Chinese relationship labels, conditional dependency guidance and the separate complete-flow check.
Version/digest diagnostics remain in Settings. When the inventory reports no Active or unavailable
configuration, its contextual Settings link preserves the originating family; normal sidebar
Settings remains available. Authentication/read errors retain the shared read-only recovery boundary.

Add/Copy/Edit opens a centered card above the originating inventory; existing edit links, refresh
and reconnection reopen the exact object with immutable edit ID. Settings and object-local tests
have separate areas, preserving their inputs and evidence. Unsaved close offers Continue editing
or explicit Discard; in-flight Save blocks unsafe exits and duplicate submission. One checked Save
publishes the focused successor and returns to the list with the known publication fact, preserving
unrelated hidden configuration and prior Active/input on known failure. A failed list read
does not undo publication. Unknown publication retains the exact submitted request through close,
reopen and refresh; explicitly verify current state before another submission. Adopt current values
or retain input after recheck pairs that choice with its verified Active context; no automatic replay.
Failed reference-impact evidence blocks removal; navigation/tests do not publish.

Family-local tests validate only the exact non-Active object and necessary inputs/references using
production engines. Only Overview offers the complete-flow check of published Active; unsaved
card candidates are never silently substituted into it. Offline tests call no Provider/media
Storage, explicit live Metadata uses the configured Provider, and neither grants execution or
publication. [Product Experience](product-experience.md#object-scoped-tests-and-complete-flow-checks)
defines each test's input/result/recovery; C remains C under A policy reuse. Save still checks the
whole successor and applicable evidence, not merely local success.

New Classification uses MediaLibrary ID plus safe path without a name/ID prefix; labelled legacy
`library/path` remains until explicit impact-acknowledged checked conversion. Preserve its path and
all historical pin semantics. Scanner/manual discovery consume the same pinned filters/depth and
real elapsed stability policy. Forms retain tab-scoped correctable values, never credentials or
runtime authority. Empty/partial graphs explain missing dependencies without generating policies.

### Metadata query type and saved identity

MetadataPolicy uses only `mediaQueryType` (`movie`, `tv`, `auto`, `none`) to decide which Provider
lookups and resolved identities are permitted. The movie/tv type on a candidate, Recognition Result
or MediaIdentity belongs to that result and drives the Provider detail call, naming and
classification; it is not a policy setting. Legacy policy `mediaType` input is accepted and ignored,
and a missing `mediaQueryType` reads as `auto`. A policy `none` performs no lookup, while a
source-linked, type-complete offline identity may still be planned without inventing a Provider
identity. Saving or re-analysing a choice performs no Storage mutation.

Automatic title search for TV files with an explicit second or later season and episode numbers
keeps the filename year as evidence and searches across series premiere years. The final score
includes bounded evidence from verifying the season and every requested episode. The configured
`confirmationThreshold` and `automaticThreshold` govern correction, candidate selection and automatic
matching within the existing Provider request budget.

Each new organize identifies its source again. A prior same-version Result, evidence row or saved
candidate is not copied into the new item's metadata choice; the pinned RecognitionType and its
`mediaQueryType` run the ordinary identification. The same source-grounded identities stay available
as bounded `allowedMetadataIdentities`; only after the operator selects and saves one for this item
does the analysis use that Provider ID and its real movie/tv type. The current Task's re-analysis
reads the correct movie or TV detail interface and the summary reuses the persisted identity, so a
saved selection is not confirmed twice or looked up again by the summary stage. A replaced source
version or a different Active revision never inherits the earlier candidate authority.

In the Files organize dialog and Task Center metadata recovery, explicit candidate search uses
the current title, movie/TV type and year from that file's correction form. A year must be an
integer from 1870 through 2100; clearing it removes the year restriction. Changing any search
condition clears earlier candidates and their selection. An invalid year keeps the inputs and
shows how to correct or clear it before searching again. Search is read-only; the separate Save
and re-analysis action uses the same query inputs or the explicitly selected candidate, followed
by exact-summary confirmation before execution. Candidate browsing does not imply an automatic match.

## Automation engine settings (native, focused)

### CURRENT — Three system runtime settings (Slice47 PASS / CLOSED)

Under `V2-TASK-011`, use the existing `/configuration` System Settings page as the ordinary
editor for the remaining three fields. Remove Automation's settings tab/form and duplicate ordinary
editors; its old settings links navigate to System Settings. Reuse the focused settings API and
checked publication; the historical API/key names do not make these Automation-only settings.

| Field | Selected meaning |
|---|---|
| `automation.maximumActiveJobs` | Integer 1–10000; shared organizing Task capacity across Files/direct CLI/API/remote, due/Run once and same-Task machine-work re-entry, not thread/file parallelism. Ordinary asynchronous copy/move/delete keep their existing admission rules. |
| `automation.workerPollSeconds` | Finite positive seconds; shared Worker's idle checks for organizing and both library kinds' ordinary asynchronous file work. |
| `automation.schedulerPollSeconds` | Finite positive seconds; checks for due Automation definitions only, not manual/Run once submission, definition Cron/interval/timezone or notifications. |

One Save publishes only these three fields from the exact observed Active, preserving unrelated
settings, runtime preparation, atomic activation, submission reconciliation and truthful actual
adoption/override evidence. Capacity-full preserves existing work/choices/authority; release
allows an explicit retry or the next due check. Save itself starts no media operation.

Delete `automation.staleJobAgeSeconds` from editable/effective/default settings and runtime arguments.
Reject explicit field edits to it without publication; existing immutable documents may retain it
and remain readable with the value ignored, without rewriting digest/pins or requiring manual JSON
cleanup. Keep current Worker heartbeat, per-runner claim expiry/renewal and individual Provider/Storage
timeouts. No no-progress observer, whole-Task timeout or automatic uncertain replay is selected.
This accepted contract replaces the Automation-only/four-field plan; prior acceptance remains in Git.

### Checked publication and actual adoption

The existing `/configuration` System Settings page renders the one three-field form and
readback (`AutomationSettingsPanel`); the Automation workspace no longer has a settings tab, and
`?tab=settings` is an ordinary unknown Automation tab with no redirect, special handling or work
submission. System Settings is reached from its current `/configuration` navigation entry.
No second store or editor exists. `GET/PUT /api/operations/automation/settings` serves the
projection and the checked Save with READ / MANAGE_CONFIGURATION enforcement.

The compact form keeps each field's meaning and backend constraints beside its input. Published
and adopted states stay separate; healthy instance details and diagnostic identities start folded,
while adoption problems and their next actions remain visible. General engine/schedule tutorials
and JSON examples are omitted from this focused settings surface.

One Save publishes only `automation.{maximumActiveJobs,workerPollSeconds,schedulerPollSeconds}`
from the observed immutable Active. Other settings and definitions are preserved byte-identically,
the whole candidate is validated, and the runtime binding is prepared before atomic activation. An
unchanged save publishes nothing. Out-of-scope keys, booleans, fractional integers, non-finite and
out-of-range values are rejected before a candidate exists. The wider field set uses the same direct
publication through `高级配置`; there is no separate Draft validate/activate journey.

Publication and adoption are reported as separate outcomes. Each live resident instance publishes
its own adopted values, the publication identity it adopted, freshness and any explicit
CLI/deployment override. Unreported, stale, stopped, mixed-version and overridden instances never
form a collective "deployed" claim, and the shared-capacity field carries an API-local basis
instead of being attributed to a resident process.

A healthy consumer whose value did not change re-writes its own report on the bounded refresh, so a
live-but-idle process is not reported as stale merely because nothing changed; a failed report write
is retried at the next boundary and never acknowledged as adopted. An unknown Save outcome is
resolved by the *submission identity* the browser sends with each Save: the reconciled answer is
`committed`, `superseded`, `not_committed` or `unresolved`, derived from that request's own durable
revision and activation evidence. Equal values alone — or another writer publishing the same values —
never certify a submission that did not publish, and only a terminal proof clears the resubmission
block. The retained submission context (identity, submitted values and the publication identity the
form was edited against) survives a reload, is principal-scoped, and never stores a bearer token.
Typed group apply, full-document JSON publish, portable-package import and corrupt-Active replacement
share this per-request read-only reconciliation; a reconnect shows both that request's result and the
current Active. The form follows a newly read Active when it has no typed input; with edits in progress
it keeps the exact input, focus and edit baseline, updates untouched fields and marks a field changed
by another session.

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
editor does not probe or mutate a Storage while applying its checked candidate. The Files-page
ResourceLibrary save is the explicit page-local exception: it runs the existing bounded checks and
activation workflow as one backend command, and it still does not mutate media Storage.

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
new submission. For genuine setup-required state, the Storage page offers the current System
Settings (`/configuration`) empty-configuration handoff and returns to refreshed Storage truth. No
direct database edit, configuration reset or physical-file migration is required.

[config/alist.example.json](../config/alist.example.json) is the secret-free OpenList Storage
template. Append its `storage` object to the generated `mediaflow.activation.json`'s `storages`,
replace `options.baseUrl` with the real service address, and provide `OPENLIST_TOKEN` only in the
deployment environment where the Storage is actually checked or used. Connection fields belong
under `Storage.options`; the retired top-level spelling fails import with the correction. Import
reuses the `config publish --file` command above and validates and publishes the complete document
directly. An unreferenced OpenList template is not contacted; once a ResourceLibrary references the
Storage, the same read-only Storage check runs as part of publication and needs that deployment's
address and credential.

### OpenList metadata and content reads

OpenList `stat`／`exists` use `/api/fs/list` to locate the exact entry in its parent directory,
following the configured page size. The configured Storage root is checked by listing itself.
Directory requests use `refresh: false` and OpenList's existing cache.

`read` obtains a download link through `/api/fs/get` and then streams the content. NFO parsing,
Hash checks and transfers between different Storages read content when their operation requires it.
Same-Storage native Move／Rename uses directory metadata for source, conflict and result checks.
A successful result includes target verification and, for Move, confirmation that the source is gone.

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
Provider, Planner, Executor or Task. They calculate or explain behavior only. Per-Storage setup
checks and the provider-neutral destination precheck construct a read-only Storage view and use
bounded read-only operations such as `List`/`Exists`/`Stat`; they do not create directories, write
files, move, copy, delete, scan recursively or grant execute authority. The older Local setup check
remains a Local diagnostic with the same read-only boundary. Live Strategy Test is the deliberate
exception for Provider access, and an explicit Webhook test sends one bounded signed request to the
configured endpoint. Neither starts media work, creates an Outbox delivery nor performs Storage
mutation.

### Notification checks and application

The Notification form works on the current object. An explicit signature test sends one request
using exactly the current form's address and secret reference, and changing either invalidates that
test. After the required test succeeds, `应用更改` validates and publishes that one object as the new
Active, refusing sibling-definition or unrelated configuration changes. Ordinary checks and apply
send no notification. The complete form context, explicit apply and concurrent/unknown-result
recovery belong to the
[notification journey](product-experience.md#notification-definitions-and-deliveries).

### Checked activation

The guided checked path requires current evidence for the exact candidate:

1. the candidate is successfully validated;
2. the applicable Recognition Strategy Test is complete;
3. every applicable enabled Storage referenced by a ResourceLibrary or MediaLibrary has passed its
   current provider-neutral read-only Storage check; and
4. when a MediaLibrary destination is declared, the current provider-neutral destination precheck
   is successful.

Before publishing, the server rechecks the Active baseline, applicable candidate evidence and
dependency validity. The new snapshot and publication audit are committed atomically.

## Web, API and CLI surfaces

Authenticated surfaces share application behavior/RBAC/audit: exact Active/successor lifecycle,
objects/reference impact, versioned secret-free configuration/result exchange, Settings and Rules,
bounded tests/checks/organizing analysis, library Save, live Files/maintenance, Task/TaskItem/results, review/recovery,
Worker readiness, Automation execution intent/occurrences and Webhook delivery recovery.
[Product Experience](product-experience.md) owns complete ordinary journeys; [Architecture](architecture.md)
owns execution and [Deployment](deployment.md) runtime administration. Configuration reads/tests/
publication create no media work. Notification retry/requeue changes only that delivery, not media.
FileIndex is removed. CLI/Files/MediaLibrary share live Storage browsing; exact source and plan
evidence remains scoped to explicit work. No independent Scan or Preview product remains.

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
mediaflow organize --limit 20
mediaflow organize --execute --limit 20
```

Parsing, recognition, metadata lookup, naming, classification, planning and Organize DryRun do not mutate
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
statuses. Repositories reject newer unsupported schemas; same-version restore follows the
explicit [deployment maintenance procedure](deployment.md#backup-and-same-version-recovery).
Old-task/Job conversion and cross-version upgrade/rollback are outside current support.
Do not infer a feature or permission to rebuild user data from an old schema number.

Published V2 configurations and the supported Storage, library, rules, system settings, Automation
and notification data retain their identities, relationships and digests. Existing Tasks keep their
pins, results and audit history. Completed or uncertain effects retain their recorded outcomes.
For configuration schema 11, use the [explicit data switch](#previous-store-data-switch) before
starting the current version. The [deployment boundary](deployment.md#boundary) and
[release validation](release.md#current-v2-validation-boundary) describe supported recovery.

## Current limitations

Provider switching/new Providers, built-in users/sessions/OIDC, general Secret Store/Docker Secrets,
automatic uncertain replay and historical rollback remain outside the accepted baseline. No arbitrary
host paths or mutation-based capability probes. Native Settings, Rules and Slice43's Automation
workspace are delivered on the sole current V2 Web surface. Task Center is organizing-only with
eight views and four business recovery types; ordinary file work stays on its originating library page.
Checked Enabled publication supplies scoped scheduled intent. [Automation creation/editing](product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)
uses the same list-background card: default-disabled creation can explicitly enable, and later editing
can enable/disable with the shared compact switch and Save. Copy is beside Edit in the list, creates
a disabled definition with a new ID, and retains an edit/reconciliation entry even outside current
filters. It uses saved values and their matching publication baseline, never unsaved editor input.
The list's Run once directly submits the saved bounded scope under
current permissions; publishing itself starts no media work. Scan/Preview/FileIndex retirement remains intact.
Production uses Waitress `api serve-production`; standard-library `api serve` stays trusted-loopback.
See [Roadmap](roadmap.md), [Progress](progress.md) and [Deployment](deployment.md) for their own facts.

### Operational setting meanings

The existing System Settings page is the one ordinary three-field publication and readback surface;
the Automation workspace has no separate settings tab. Adoption checks every fresh live Worker/Scheduler instance separately.
Stopped/expired registrations remain bounded diagnostic history with a true total; a healthy
replacement can complete adoption without deleting history. Absent live consumers, unreadable
evidence and live overridden/pending instances keep collective adoption unproven with recovery guidance.

The table below describes accepted CURRENT behavior. Slice47 records the independent B/A
acceptance, actual artifact evidence and validation limits; no production deployment is claimed.

| Setting | Current code / accepted baseline meaning |
|---|---|
| `workflowRetry` | `enabled` defaults false; `baseDelaySeconds`/`maxDelaySeconds` bound backoff. Read-only retry covers normalized timeout/connection/rate-limit/temporary-provider failures before planning/execution. `maxAttempts` 1–10, `maxDelaySeconds` ≤300, `jitterRatio` 0–1; never retries mutation/uncertain effects or grants execute authority. |
| `automation.maximumActiveJobs` | Default 100, range 1–10000; one atomic shared organizing Task allowance, not worker parallelism. Files, current API and CLI admissions, due/Run once and same-Task machine-work re-entry share it. Ordinary asynchronous copy/move/delete use their own admission rules. Terminal or wholly human-waiting work releases its slot. Lowering it blocks new excess admissions and preserves already admitted work. Published through the three-field System Settings Save; admission/re-entry reads the current Active. |
| `automation.staleJobAgeSeconds` | Retired: not editable, validated, effective or generated in new defaults. An existing immutable document may retain the key and remain readable with the value ignored; field edits to it are refused with zero publication. Current heartbeat, lease/renewal and Provider/Storage call timeouts remain unchanged. |
| `automation.workerPollSeconds` | Finite positive seconds; the real resident Worker loop cadence, independent of heartbeat/lease and of any Task's media pin. A running Worker adopts a new value at its next safe loop boundary without a restart. Configuration/heartbeat/report wakes are bounded to at most 5s so a previously long value cannot defer adoption, while the business claim cadence itself stays at the selected value — a recheck never claims early. `--poll-seconds`/deployment overrides keep precedence and are reported as overrides. |
| `automation.schedulerPollSeconds` | Finite positive seconds; the real resident Scheduler due-check cadence. It never changes any definition's interval, Cron expression or timezone, and adopts without restart under the same boundary/recheck rules and override precedence. Bounded configuration wakes do not tick the interval/due check early. |
| Focused engine-settings Save | One checked Save publishes only these three fields from the observed Active, after whole-candidate validation and runtime preparation. A no-op Save publishes nothing. While the Save is outstanding the three inputs are read-only; a value that still races the response is retained and re-based onto the just-published identity. An unknown outcome blocks further saves until its own durable evidence resolves it; a submission that terminates without publishing (a three-field input refusal, a stale/no-op refusal or a persist/validate/prepare/activate fault) records a bounded terminal outcome, so reconciliation ends in a correctable state with the typed input kept. Recovery merges **only the fields the operator changed** into the latest published values, so another writer's change to an untouched field is preserved; a genuine same-field overlap shows both values with units and needs an explicit "use current" / "keep mine" choice before Save is enabled. The next Save is always checked against the latest published identity. An input refusal (for example `3.5` for an integer field) keeps its invalid text correctable and is proven from a bounded content fingerprint rather than by re-validating an unpublishable payload. |
| Organizing Cron schedules | Validated five numeric fields with IANA timezone; `*`, lists, inclusive ranges and positive steps, no seconds/names/macros/shell/catch-up backlog. Missing DST wall times skip; ambiguous wall time fires once. Managed Automation Task Definitions are the only scheduled input: checked Enabled publication supplies scoped scheduled intent under V2-AUTO-010; live permissions and full plans/checks still precede effects. The retired `automation.schedules` product accepts no schedule definition: a system-generated empty slot in a normal V2 document stays readable with no scheduling semantics, and any schedule definition rejects through normal validation. Run once is a separate explicit command and never advances due state. Independent Preview schedules are unsupported. |
| Organize Hash/attachments | Hash defaults NONE with zero reads; FAST is bounded prefix evidence, FULL is bounded streaming. Failed/unknown comparison adds a conflict and never authorizes overwrite/delete. Opt-in attachments are matched only in the primary directory; unknown files are not included/cleaned. |
| Source cleanup / rollback | Cleanup defaults none; only fully verified successful MOVE may clean bounded ancestors below the exclusive ResourceLibrary root. `rollback.enabled` defaults false, `cleanupCreatedDirectories` true; compensation covers only this invocation's verified effects, never changed targets, reappeared sources or older executions. Complete policy constraints remain in Requirements. |
