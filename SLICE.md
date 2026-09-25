# Slice 39 — Storage Management Workspace

This is the A-owned Contract for the V2 Storage management journey. It turns the existing
managed Storage object and adapter capabilities into the operator-facing workspace represented by
`docs/pics/储存管理.png`. The image is a visual and business-flow reference only; its names, counts,
paths and example records are synthetic fixture data and are not product truth.

```text
Slice ID: 39
Name: Storage Management Workspace
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: d02539e49d5c99c3e3c0c70de5e994e42824a18e
Implementation Head: NOT SET
Contract Revision: 2026-09-25 A initial activation — V2 Storage management journey
```

Slice 38 is `PASS / CLOSED`. Its Base, Implementation Head, Closure Packet and A Final Review are
historical facts and remain unchanged. This Slice starts from the repository HEAD immediately after
that closure. It does not reopen MediaLibrary/ResourceLibrary Files, replace the Storage adapters,
or redesign the general Configuration page.

## User Goal

An authenticated, authorized operator can understand which Storage locations MediaFlow is configured
to use, add or maintain one safely, see which libraries depend on it, run a bounded read-only check,
and recover from invalid or unavailable configuration without confusing a Draft with the runtime
Active configuration or changing media contents.

## A Scope Decisions

- Add a supported V2 route at `/ui-v2/storage`; the full route is owned by the Storage management
  navigation item and is distinct from `/ui-v2/configuration`, which remains the general
  Configuration/System Settings migration handoff.
- Make `docs/pics/储存管理.png` the visual reference for hierarchy and interaction: shared light
  shell, page title/subtitle, provider summary cards, Storage table, and right-side four-step
  Add/Edit drawer. The screenshot's values are synthetic and must never be hardcoded as runtime
  data or used as acceptance counts.
- Compose the page from the existing Managed Configuration and `ConfigurationObjectService`
  authority. The page must not create a second Storage repository, adapter registry, or Active
  source of truth.
- Support the existing V1 Storage kinds through one provider-neutral page: Local, SMB, OpenList,
  AWS S3, Cloudflare R2 and generic S3-compatible. `S3 / R2` may be one visual family, but the
  persisted type and provider-specific validation remain distinct.
- Use a page-local Save convenience for Add/Edit/copy/enable/disable: the server composes a
  successor from the exact current Active snapshot, performs complete validation and applicable
  checked read-only evidence, and publishes the successor atomically only on full success. The
  operator does not copy revision, digest, token, claim or fence identifiers.
- Keep the general Draft/Validate/Activate lifecycle, import/export, audit and support paths
  available through the existing Configuration authority. This Slice does not redesign that page.
- If the instance is in management-only bootstrap, has only `JSON_BOOTSTRAP` authority, or has no
  valid Active workflow snapshot, show a truthful setup/handoff state. Do not present a partial
  Storage object as Active and do not silently activate an incomplete document. Existing first-time
  setup and compatibility Web journeys remain the recovery path until a complete managed runtime
  exists.
- Treat `Connection` and `Read` checks as bounded, zero-mutation diagnostics bound to the exact
  candidate revision. Mutation-based write probes, probe cleanup and capability-discovery writes
  are explicitly outside this Slice; a UI/API must not imply that a read-only check proves write
  access.

## Baseline and Applicable Requirements

At Base, the Python domain, adapters, managed configuration persistence, generic object CRUD API,
reference protection, Storage check evidence, Storage Browser and checked activation already exist.
The V2 Storage navigation item still points at a generic migration placeholder, and there is no
Storage page, typed Storage projection, provider form, page-local Storage Save flow or Storage
management browser proof.

Applicable stable requirements include `REQ-STO-001` through `REQ-STO-007`, `REQ-CONFIG-001` through
`REQ-CONFIG-010` and `REQ-CONFIG-012`, `REQ-WEB-001`, `REQ-WEB-004`, `REQ-WEB-005`, `REQ-WEB-006`,
`REQ-WEB-007`, `REQ-API-001` through `REQ-API-003`, and `REQ-SAFE-004` through `REQ-SAFE-007`.
The canonical Storage definition, adapter capability model, path semantics, credential redaction,
reference blocking and immutable Active rules remain authoritative.

The page is a configuration journey, not a Files journey. It must not use FileIndex, scan a
ResourceLibrary, invoke a Metadata Provider, calculate a media plan, or execute an Organizer task.

## Operator Journey and UX Constraints

| Stage | Required experience |
|---|---|
| Goal | Understand and safely maintain the Storage locations used by libraries and runtime. |
| Entry | Choose `存储管理` in the shared V2 shell or open the supported Storage deep link after authentication continuation. |
| Visible state | Page title/subtitle, bounded provider summary counts, search/filter state, Storage identity/type/location, enabled/read-only state, bounded connection/readiness state, references, current configuration authority and actionable setup/error state. Secrets and unsupported raw paths are never shown. |
| Action | Search/filter, inspect details/references, add, edit, copy, enable, disable, delete after reference check, and explicitly run an advertised zero-mutation Connection/Read check. |
| Success | The intended successor becomes the actual immutable Active runtime configuration; the list refreshes from the same authority, reference facts are current, and no media content changes. A read check records bounded evidence without activating or creating work. |
| Failure | Invalid ID/name/provider fields, duplicate identity, missing secret reference, invalid root/endpoint, unavailable/denied/timeout provider, stale Active, failed evidence, blocked reference, activation conflict or runtime-load failure identifies the affected object and durable state without exposing secrets. |
| Recovery | Correct the named field, secret reference, deployment mount or provider availability; refresh stale authority; rerun the bounded read check; repoint dependents before removal; or follow the existing setup/Configuration handoff. Failed saves retain correctable input and preserve the previous Active runtime. |

The page follows the existing light V2 shell and project design system: a fixed left navigation rail,
top search/account bar, restrained white/light-gray surfaces, blue primary actions, green enabled
state, compact rounded controls and a dense table for repeated operations. It is a work surface, not
a marketing page. Cards and drawer content must remain usable at narrow widths, preserve keyboard
focus, and expose accessible names and deterministic empty/loading/error states.

## Required Surfaces

- `/ui-v2/storage` with the shared shell, active `存储管理` navigation item, page-local search and
  bounded provider summary cards.
- A Storage table with name plus stable ID, type, root/location, enabled/read-only or diagnostic
  state, bounded ResourceLibrary/MediaLibrary reference summary and actions.
- A Storage detail/readiness view or drawer that shows provider-safe fields, capability declarations,
  secret-reference readiness, exact configuration authority and reference impact without secret
  values or unbounded host access.
- A four-step right-side Add/Edit drawer: `基本信息 → 连接配置 → 高级设置 → 确认`. Edit is
  prefilled from one exact Active object; the ID is visible and read-only. Cancel, close and Escape
  restore focus where practical; failed submission retains correctable values.
- Typed provider forms for Local, SMB, OpenList, S3, R2 and S3-compatible settings, plus common
  enabled/read-only, timeout, retry/concurrency, root and bounded notes/configuration metadata where
  the canonical object supports them. Provider credentials are entered as approved secret
  references, never as values returned by the API.
- Bounded reference inspection for libraries that use a Storage. The normal table may show counts;
  details must identify the affected dependents sufficiently for a safe repoint/remove decision.
- Read-only Connection/Read check status, evidence currentness and safe retry/recovery. A check never
  scans recursively, starts a Task, calls a Metadata Provider, mutates Storage or grants execution
  authority.
- Matching typed API behavior for list/detail/reference, Add/Edit/copy/enable/disable/delete and
  checks. Web is not allowed to bypass the existing API permission, validator, audit, evidence,
  concurrency or activation rules.

## Required Outcomes

### RO-1 — V2 Storage route and reference-aligned workspace

The Storage navigation item resolves to `/ui-v2/storage` and is the only active shell item there;
System Settings/general Configuration continues to have its own route and migration semantics.
The page composes the image's hierarchy: title/subtitle, `+ 添加存储`, provider summary/filter cards,
search, Storage table and right-side drawer. Summary counts are derived from bounded configuration
objects, never from a recursive Storage scan or fabricated capacity data. The fixture values in the
reference image are not runtime literals.

### RO-2 — Truthful bounded Storage inventory and explanation

An authenticated viewer can list enabled and, where permitted, disabled Storage objects in stable
order, search by name/ID/type/location/notes, filter by provider family, inspect exact bounded
configuration status and see which ResourceLibraries and MediaLibraries reference each object.
Local roots are execution-environment paths under backend confinement; remote roots are logical
provider-relative paths. The projection redacts credentials, authorization headers, cookies,
tokens, access keys and secret values. It distinguishes missing/unavailable data from success and
does not require a Storage read merely to render the configuration list.

### RO-3 — Add/Edit with provider-specific validation and checked Active publication

The Add/Edit drawer captures the complete supported Storage object without JSON-only editing:
identity/name/type, Local or remote root, provider fields, approved secret references, enabled and
read-only state, timeout/retry/concurrency settings and bounded notes if present in the canonical
model. IDs satisfy the backend identifier rule and are immutable after creation. Provider forms
show only fields valid for the selected type while preserving unexposed existing options on edit.

Save binds to the exact Active revision used to open the form, validates the complete dependency
graph, runs current applicable read-only Storage evidence, and atomically activates only a complete
successor. A successful change is immediately reflected by the same Active list and is usable by
subsequent library/configuration work. A stale writer, duplicate ID, invalid root/endpoint,
missing/unavailable secret reference, permission failure, evidence failure or runtime-load error
leaves the previous Active and current Storage contents unchanged; entered values remain correctable.

### RO-4 — Safe copy, enable/disable and removal semantics

Copy requires an explicit new ID/name and copies only the safe configuration/secret references, not
secret values. Enable/disable and delete are explicit actions bound to current authority. Disabling
or removing a Storage with active library dependents is rejected or clearly blocked by graph
validation with the affected references and a repoint/re-enable recovery path. Removing a Storage
configuration never deletes, moves, renames or tests its physical root contents. Unknown mutation
outcomes are verified from current Active state and never automatically replayed.

### RO-5 — Bounded read diagnostics and operational state

The operator can explicitly run the advertised zero-mutation Connection/Read check for one Storage
against the exact candidate/runtime revision. The result records provider-safe status, affected
Storage identity, bounded operations/evidence, currentness, failure category and next action. It
uses the least authority needed, respects configured read-only intent, capability declarations,
timeouts/retry limits and path confinement, and never claims write support from a read check.
The page exposes no mutation-based write probe in this Slice; that omission is visible as an honest
unsupported/deferred capability rather than a false green status.

### RO-6 — Actionable failure, recovery and security boundaries

Missing Active/management bootstrap, 401/403, malformed payload, provider timeout/authentication,
missing local mount, root escape, stale revision/digest, activation conflict, referenced deletion,
unsupported provider capability and failed check each render a stable, action-oriented state. The
operator can tell what remains durable, what did not happen, whether a safe read check can be rerun,
and which explicit action continues recovery. No raw exception, secret, host-wide filesystem
listing, internal execution token or arbitrary revision protocol is required in the ordinary Web
journey.

### RO-7 — Shared authority, API parity and regression isolation

Web and API use the same application service, RBAC, validation, optimistic concurrency, exact Active
binding, reference protection, redaction, audit and error categories. Existing V1 `/ui`, generic
configuration/import/export, Storage Browser/path selection, Files/MediaLibrary routes, Operations,
Storage adapters and OrganizerExecutor behavior remain compatible. Storage page reads never create
Tasks, scan, call Providers or mutate Storage; only existing explicit organizer/file-command paths
retain mutation authority.

## Safety and Correctness Invariants

1. Storage adapters remain behind the domain/application Storage ports. The page never calls a local
   filesystem, SMB client, OpenList HTTP API or S3 SDK directly.
2. Every location remains identified as `Storage ID + Storage-relative path` where applicable.
   Local host/container absolute roots are accepted only through existing backend confinement;
   host `/`, Docker socket, unmapped host paths and arbitrary browser paths are rejected.
3. Storage list/detail, form open, validation, reference lookup and read checks are zero-mutation.
   No page render, filter, search, save failure or refresh starts scanning or media work.
4. Only the existing OrganizerExecutor boundary may perform Storage mutation. This Slice adds no
   mutation-based capability probe, fallback operation or hidden write/delete cleanup.
5. Storage capability declarations are advisory facts checked by the existing planner/executor
   boundary; unsupported operations never silently fall back.
6. `Active` means the exact immutable runtime snapshot consumed by runtime. A Draft, revision row,
   saved JSON object or stale process copy is never shown as Active merely because it exists.
7. Add/Edit/copy/enable/disable save only through checked, atomic successor publication. A failed
   validation/evidence/activation/runtime load preserves the former Active pointer and current
   Storage contents.
8. Optimistic concurrency rejects stale writers. Existing admitted work remains pinned to its own
   snapshot; a Storage edit never silently rebinds or rewrites in-flight work.
9. References to ResourceLibraries and MediaLibraries are bounded, deterministic and secret-free.
   Referenced deletion or disabling cannot bypass graph validation and never cascades to library or
   physical-file deletion.
10. Credentials and secret references are never returned as secret values and never appear in
    normal logs, audits, errors, exports, diffs, screenshots or test fixtures. Configuration copy
    and detail retain only approved redacted/readiness projections.
11. RBAC and API/Web parity are backend authoritative. Viewer/read-only principals cannot mutate
    configuration; management actions record bounded actor/before/after/result audit evidence.
12. Unknown results are not automatically retried. A read check may be explicitly rerun only after
    its durable state and safe repeatability are clear; save/activation never silently replays.

## Explicitly Deferred / Excluded

- Mutation-based Storage write/capability probes, probe cleanup, test-object retention and recovery
  after an uncertain probe. This Slice deliberately delivers only zero-mutation Connection/Read
  checks; a future capability-diagnostics Slice must design the explicit mutation authority first.
- General Configuration page migration/redesign, full Draft/Validated/Active administration UI,
  configuration import/export, backup/restore, System Settings and Webhook management.
- New Storage providers (WebDAV, SFTP, FTP, OSS, COS or other adapters), provider switching and
  complete Secret Store/Docker Secrets integration.
- Storage Files/FileIndex browsing, ResourceLibrary/MediaLibrary file operations, scanning, parsing,
  recognition, metadata, naming, classification, organizing, thumbnails, capacity/full-library
  statistics and media playback.
- Arbitrary host filesystem browsing, recursive root scans, content indexing, upload/download or
  automatic root directory creation. Existing bounded Storage Browser/path selection remains a
  separate setup/configuration capability.
- Changing Storage IDs, migrating or copying physical root contents after configuration changes,
  automatic reference rewrites, bulk multi-object editing, policy editing, V1 `/ui` retirement or
  a new identity/session system.
- Changes to the user's dirty files under `docs/pics/`; the supplied `储存管理.png` remains a
  reference asset only and is not rewritten or committed by implementation Tasks.

## Slice Acceptance Criteria

| ID | Acceptance |
|---|---|
| AC-1 | `/ui-v2/storage` is a real authenticated route with the shared light shell, correct active navigation, search/filter state, synthetic-data-independent summary cards and responsive drawer/table composition. |
| AC-2 | Storage inventory and detail projections are bounded, deterministic, reference-aware, provider-safe and secret-free; Local/remote path identity and authority are not confused. |
| AC-3 | All six supported Storage configurations can be added and edited through typed provider forms; ID immutability, field preservation, validation and approved secret references are enforced by API and Web. |
| AC-4 | Successful Add/Edit/copy/enable/disable publishes an actual checked Active successor; stale/invalid/denied/evidence/runtime failures preserve prior Active, current Storage and correctable input. |
| AC-5 | Referenced Storage removal/disable is blocked or explained with current dependents; unreferenced configuration removal never touches physical content and unknown results are not replayed. |
| AC-6 | Explicit zero-mutation Connection/Read checks show current/bounded evidence, provider-safe errors and recovery; no read check claims write capability and no write probe appears in this Slice. |
| AC-7 | API and Web share permissions, application behavior, redaction, audit, lifecycle and error/recovery semantics; existing V1/V2 journeys and adapters remain green. |
| AC-8 | Controlled screenshots at `1536 x 1024` with drawer step 1 open and closed, plus narrow-screen/keyboard/focus evidence, demonstrate the reference hierarchy and operable controls without treating pixel equality or sample data as truth. |
| AC-9 | Final Base..Head evidence covers focused and full regression, browser journeys, typecheck/lint/format/build, governance, secret/private-file audit, FFmpeg/FFprobe exclusion and any configuration/packaging gates material to changed persistence or API composition. |

## Final Validation Expectations

This Slice crosses Active configuration, RBAC, credentials/redaction, concurrency, API and Web, so
Tasks touching those boundaries require the workflow's T4 validation level. B assigns each Task's
level from actual risk; the Slice gate normally includes:

- focused Python tests for provider validation, redaction, references, exact Active concurrency,
  checked read evidence, error categories and zero Storage mutation;
- focused Web entity/API/component tests for typed projections, form transitions, filtering,
  error/recovery, accessible menus/drawer focus and provider-specific fields;
- Playwright journeys for authenticated success, Add/Edit/copy/enable/disable/remove, referenced
  blocking, stale/failed activation, read-check failure and setup/unavailable handoff;
- controlled fake/local Storage services and temporary test roots only; no production SMB/OpenList/
  S3/TMDB service, credential or user media;
- normal Python regression, Web tests, typecheck/lint/format/build, `git diff --check`, governance,
  private/config audit and FFmpeg/FFprobe exclusion checks; packaging/migration/release smoke only
  where the actual implementation changes those boundaries.

Visual evidence uses `docs/pics/储存管理.png` as structural/design-intent reference at `1536 x 1024`.
The check must include drawer-open and closed states, long provider forms, empty/loading/error
states, narrow width and keyboard/focus behavior. Nonzero raster differences and the screenshot's
synthetic records are not independent blockers; hierarchy, labels, state truthfulness and working
controls are.

## Delegated Factual Updates and Stop Rule

B may replace the explicit no-active Task notice with one coherent Task after this Contract and its
`ACTIVE` Roadmap row are checkpointed. B may update factual implementation-head, test and Task review
evidence delegated by this Contract, but cannot expand provider scope, add write probes, weaken
Active/reference/safety rules, change Base or declare the Slice closed.

After every Task PASS, B must reevaluate RO-1 through RO-7. Once all Required Outcomes and acceptance
criteria are satisfied, B stops planning, emits the Closure Packet with decision `SLICE READY FOR A
REVIEW`, and leaves A to review Base..Head and reconcile CURRENT documents. P2 wording, optional
visual polish or a future write-probe idea is not a reason to create another Task.

## NO ACTIVE IMPLEMENTATION TASK

```text
Parent Slice: 39 — Storage Management Workspace
Status: NO ACTIVE IMPLEMENTATION TASK
Next Action: B plans the first coherent implementation Task after this Contract checkpoint
```
