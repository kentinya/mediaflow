# Slice 39 — Storage Management Workspace

This is the A-owned Contract for the V2 Storage management journey. It turns the existing
managed Storage object and adapter capabilities into the operator-facing workspace represented by
[储存管理.png](docs/pics/储存管理.png). The image is a visual and business-flow reference only; its names, counts,
paths and example records are synthetic fixture data and are not product truth.

```text
Slice ID: 39
Name: Storage Management Workspace
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: d02539e49d5c99c3e3c0c70de5e994e42824a18e
Implementation Head: NOT SET
Contract Revision: 2026-09-25 A review corrections — checked activation, removal, layout and reference; no notes
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
  data or used as acceptance counts. The supplied image is checkpointed unchanged with this Contract
  revision so another checkout has the same reference; textual user corrections override it.
- The user's correction overrides the image: Storage has no notes field. Do not add notes input,
  display, persistence or search. The top search placeholder is `搜索存储、路径...`; the image's
  reference to `备注` is incorrect and is not an implementation requirement.
- Compose the page from the existing Managed Configuration and `ConfigurationObjectService`
  authority. The page must not create a second Storage repository, adapter registry, or Active
  source of truth.
- Support the existing V1 Storage kinds through one provider-neutral page: Local, SMB, OpenList,
  AWS S3, Cloudflare R2 and generic S3-compatible. `S3 / R2` may be one visual family, but the
  persisted type and provider-specific validation remain distinct.
- Use page-local Save for Add/Edit/copy/enable/disable and an explicit configuration removal action:
  each operation uses the same checked publication boundary. The server composes a
  successor from the exact current Active snapshot, performs complete validation and applicable
  checked read-only evidence, prepares runtime binding, and publishes the successor atomically only
  on full success. Removal is not complete after a Draft edit alone. The operator does not copy
  revision, digest, token, claim or fence identifiers.
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

The page manages configuration. It must not use FileIndex, scan a ResourceLibrary, make live
Metadata Provider requests, create media-processing Jobs/Tasks, execute an Organizer task or mutate
Storage. Checked activation must retain its applicable exact-successor gates: read-only Storage
checks, the offline Recognition Strategy Test and destination precheck. The offline test and
destination precheck may reuse Parser, Recognition, Naming, Classification and Planner with bounded
synthetic samples and guarded Storage reads. These internal calculations and persisted validation
evidence are permitted; they create no executable media work and grant no execution authority.
The absence of a page-level Organize/Preview action never authorizes skipping these activation gates.

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

### Reference Composition and Interaction

| Region | Required composition and behavior |
|---|---|
| Shared shell and search | Reuse the existing left rail and top bar with `存储管理` active. Use the shared top-bar search input with placeholder `搜索存储、路径...` for the Storage inventory; do not add a duplicate search box to the page body. Storage search state must not change the Files or MediaLibrary search context. |
| Header | Show `存储管理` and `管理系统中的存储位置，用于访问本地文件或者各类云存储服务。` on the left, with `+ 添加存储` on the right above the cards. |
| Provider cards | Place the provider summary/filter strip above the table, with type icons, names, configuration counts and a clear selected state. Use Local (`本地存储`), SMB, OpenList and `S3 / R2` families; the S3 family retains the actual S3/R2/S3-compatible subtype in the form and data. Sample duplicate cards and quantities are not literal requirements. Filtering offers a clear way to return to all types. |
| Table | The six columns appear in this order: `名称 \| 类型 \| 根路径 / 位置 \| 状态 \| 引用情况 \| 操作`. The name cell shows a type icon and name with the stable ID on a secondary line. Root/location is configuration display, not a file-browsing command. |
| State and references | Enabled/disabled and read-only intent remain distinct from the latest check result; `已启用` is not proof of a healthy connection. Show separate `资源库` and `媒体库` reference counts in the reference cell, including disabled dependents, with an inspectable bounded breakdown. |
| Row actions | Keep `查看`, `编辑` and the accessible `更多` ellipsis menu in the rightmost operation cell, in that order where permitted. View opens the Storage detail/readiness surface; Edit opens the prefilled drawer. More contains applicable copy, enable/disable, read-check and configuration removal actions, with backend-authoritative permission and reference restrictions. |
| Drawer | Use a right-aligned white panel with a title and close control, a left step rail and a right form area. Steps are `基本信息 → 连接配置 → 高级设置 → 确认`. The inventory remains visible as context at the reference desktop width. Normal entry, reload and reconnect leave the drawer closed; explicit Add/Edit opens step 1. |
| Drawer footer | Keep Cancel, Back when applicable, and Next or final Save reachable at the bottom while long forms scroll. Closing, Cancel and Escape restore focus where practical and never submit a configuration change. A known failed Save retains correctable input; an unknown outcome offers state verification without automatic resubmission. |

Step 1 contains required `名称`, `存储 ID` and `存储类型`, in that order, with the provider choices
represented by their icon, label and short description. ID follows the backend lowercase
letter/digit/hyphen/underscore rule and is read-only on Edit. Step 2 contains the selected provider's
connection and root fields; step 3 contains enabled/read-only and supported advanced settings; step 4
shows the secret-free summary and final Save action. Back/Next preserve input, expose field errors
at the relevant step and do not activate configuration. Storage has no notes input or notes search.

At `1536 x 1024`, retain the picture's relative proportions: roughly a `208 px` shared left rail,
`58 px` top bar and a `430 px` right drawer. These are composition guides, not pixel thresholds.
Narrow layouts may reflow the step rail and table while retaining readable fields, reachable actions,
keyboard operation and focus behavior. Exact icon artwork, typography rasterization and example
data are not acceptance criteria; the hierarchy and interaction relationships above are.

## Required Surfaces

- `/ui-v2/storage` with the shared shell, active `存储管理` navigation item, Storage search in the
  shared top bar and bounded provider summary cards.
- The six-column Storage table and row actions defined in Reference Composition and Interaction,
  with name above stable ID, separate configuration/check state and both library reference counts.
- A Storage detail/readiness view or drawer that shows provider-safe fields, capability declarations,
  secret-reference readiness, exact configuration authority and reference impact without secret
  values or unbounded host access.
- A four-step right-side Add/Edit drawer: `基本信息 → 连接配置 → 高级设置 → 确认`. Edit is
  prefilled from one exact Active object; the ID is visible and read-only. Cancel, close and Escape
  restore focus where practical; failed submission retains correctable values. The drawer is closed
  on normal entry and opens only on explicit intent with the step rail, form and footer defined above.
- Typed provider forms for Local, SMB, OpenList, S3, R2 and S3-compatible settings, plus common
  enabled/read-only, root and supported timeout/retry/concurrency settings. Provider credentials
  are entered as approved secret references, never as values returned by the API.
- Bounded reference inspection for libraries that use a Storage. Table counts include enabled and
  disabled dependents; details identify their kind, identity and enabled state sufficiently for a
  safe repoint/remove decision. A truncated breakdown never implies there are no more blockers.
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
The page follows Reference Composition and Interaction: title/subtitle, `+ 添加存储`, provider
summary/filter cards, shared top-bar search, six-column Storage table and right-side drawer with
explicit opening and step-1 fields. Summary counts are derived from bounded configuration
objects, never from a recursive Storage scan or fabricated capacity data. The fixture values in the
reference image are not runtime literals.

### RO-2 — Truthful bounded Storage inventory and explanation

An authenticated viewer can list enabled and, where permitted, disabled Storage objects in stable
order, search by name/ID/type/location, filter by provider family, inspect exact bounded
configuration status and see which ResourceLibraries and MediaLibraries reference each object.
Local roots are execution-environment paths under backend confinement; remote roots are logical
provider-relative paths. The projection redacts credentials, authorization headers, cookies,
tokens, access keys and secret values. It distinguishes missing/unavailable data from success and
does not require a Storage read merely to render the configuration list.

### RO-3 — Add/Edit with provider-specific validation and checked Active publication

The Add/Edit drawer captures the complete supported Storage object without JSON-only editing:
identity/name/type, Local or remote root, provider fields, approved secret references, enabled and
read-only state and supported timeout/retry/concurrency settings. Storage has no notes field.
IDs satisfy the backend identifier rule and are immutable after creation. Provider forms
show only fields valid for the selected type while preserving unexposed existing options on edit.

Save binds to the exact Active revision used to open the form, validates the complete dependency
graph, runs the applicable read-only Storage checks, offline strategy test and destination precheck
against that exact successor, prepares runtime binding, and atomically activates only a complete
successor. It preserves the permitted internal zero-mutation calculations defined above.
A successful change is immediately reflected by the same Active list and is usable by
subsequent library/configuration work. A stale writer, duplicate ID, invalid root/endpoint,
missing/unavailable secret reference, permission failure, evidence failure or runtime-load error
leaves the previous Active and current Storage contents unchanged; entered values remain correctable.

### RO-4 — Safe copy, enable/disable and removal semantics

Copy requires an explicit new ID/name and copies only the safe configuration/secret references, not
secret values. Copy and enable/disable publish through the same checked successor lifecycle as
Add/Edit. Disabling cannot leave an enabled library with a disabled Storage binding; full graph
validation supplies the affected references and a repoint/re-enable recovery path.

Configuration removal has one explicit confirmation describing the selected Storage and the fact
that physical files remain. The backend binds the request to the exact Active revision used for
that decision, rechecks permissions and every current ResourceLibrary/MediaLibrary reference,
including references from disabled libraries, and rejects stale authority or any remaining
reference. It must not hide disabled dependents, cascade removal, or rewrite library references.

For an unreferenced Storage, removal composes a complete successor containing the other objects,
performs full graph validation and applicable checked evidence for the remaining configuration,
prepares runtime binding and atomically activates that successor. Only then may Web/API report
success and refresh the inventory/reference counts from the resulting Active configuration.
Deleting an object in a Draft alone is not success. Permission, reference, stale/concurrent,
validation, evidence, persistence or runtime-binding failure preserves the previous Active and
keeps the still-configured Storage visible with an actionable recovery explanation. No check of
the removed Storage's root is needed merely to remove its configuration. Removal never mutates
its root contents or modifies historical snapshots used by already admitted work. Unknown outcomes
are verified from current Active state and never automatically replayed.

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
3. Storage list/detail, form open, validation, reference lookup and read checks perform zero Storage
   mutation. Checked activation retains the required offline strategy and destination calculations,
   including guarded Planner use and persisted evidence against the exact successor. No page render,
   filter, search, configuration command or refresh starts scanning or media-processing Jobs/Tasks.
4. Only the existing OrganizerExecutor boundary may perform Storage mutation. This Slice adds no
   mutation-based capability probe, fallback operation or hidden write/delete cleanup.
5. Storage capability declarations are advisory facts checked by the existing planner/executor
   boundary; unsupported operations never silently fall back.
6. `Active` means the exact immutable runtime snapshot consumed by runtime. A Draft, revision row,
   saved JSON object or stale process copy is never shown as Active merely because it exists.
7. Add/Edit/copy/enable/disable/remove publish only through complete validation, applicable checked
   evidence, prepared runtime binding and atomic successor activation. A failed operation preserves
   the former Active pointer and Storage contents. Removal is visible as success only after the
   resulting Active snapshot no longer contains the selected Storage.
8. Optimistic concurrency rejects stale writers. Existing admitted work remains pinned to its own
   snapshot; a Storage edit never silently rebinds or rewrites in-flight work.
9. References to ResourceLibraries and MediaLibraries are bounded, deterministic and secret-free.
   Removal checks all existing references, including disabled libraries, without treating a bounded
   display as the whole dependency graph. Disabling cannot bypass full graph validation. Neither
   operation cascades to library or physical-file deletion.
10. Credentials and secret references are never returned as secret values and never appear in
    normal logs, audits, errors, exports, diffs, screenshots or test fixtures. Configuration copy
    and detail retain only approved redacted/readiness projections.
11. RBAC and API/Web parity are backend authoritative. Viewer/read-only principals cannot mutate
    configuration; management actions record bounded actor/before/after/result audit evidence.
12. Unknown results are not automatically retried. A read check may be explicitly rerun only after
    its durable state and safe repeatability are clear; save/activation never silently replays.

## Explicitly Deferred / Excluded

- Storage notes input, display, persistence and search are excluded by the user's correction, not
  deferred to a later Task or Slice.
- Mutation-based Storage write/capability probes, probe cleanup, test-object retention and recovery
  after an uncertain probe. This Slice deliberately delivers only zero-mutation Connection/Read
  checks; a future capability-diagnostics Slice must design the explicit mutation authority first.
- General Configuration page migration/redesign, full Draft/Validated/Active administration UI,
  configuration import/export, backup/restore, System Settings and Webhook management.
- New Storage providers (WebDAV, SFTP, FTP, OSS, COS or other adapters), provider switching and
  complete Secret Store/Docker Secrets integration.
- Storage Files/FileIndex browsing, ResourceLibrary/MediaLibrary file operations, media-processing
  workflows and page-level Scan/Preview/Organize, thumbnails, capacity/full-library statistics and
  media playback. The required offline activation checks and internal Parser/Recognition/Naming/
  Classification/Planner calculations defined above remain in scope.
- Arbitrary host filesystem browsing, recursive root scans, content indexing, upload/download or
  automatic root directory creation. Existing bounded Storage Browser/path selection remains a
  separate setup/configuration capability.
- Changing Storage IDs, migrating or copying physical root contents after configuration changes,
  automatic reference rewrites, bulk multi-object editing, policy editing, V1 `/ui` retirement or
  a new identity/session system.
- Editing or regenerating the supplied `docs/pics/储存管理.png`, which A includes unchanged in this
  Contract checkpoint. Unrelated existing image modifications, deletions and new files remain
  outside the checkpoint. Implementation Tasks consume the committed reference with the no-notes
  override; they do not alter it.

## Slice Acceptance Criteria

| ID | Acceptance |
|---|---|
| AC-1 | `/ui-v2/storage` uses the shared light shell and top-bar search, correct active navigation, provider filter cards and the specified six-column table with name above ID and `查看 / 编辑 / 更多` actions. The drawer defaults closed and explicit Add/Edit opens step 1 with name, ID and type, a left step rail, right form and reachable bottom actions. |
| AC-2 | Storage inventory and detail projections are bounded, deterministic, reference-aware, provider-safe and secret-free; Local/remote path identity and authority are not confused. |
| AC-3 | All six supported Storage configurations can be added and edited through typed provider forms; ID immutability, field preservation, validation and approved secret references are enforced by API and Web. Storage forms, API configuration and search omit notes, and the search placeholder is `搜索存储、路径...`. |
| AC-4 | Successful Add/Edit/copy/enable/disable/remove publishes an actual checked Active successor with runtime binding; required offline strategy/destination calculations are retained. Stale/invalid/denied/evidence/persistence/runtime failures preserve prior Active, Storage contents and correctable input or removal context. |
| AC-5 | Removal rejects every remaining ResourceLibrary/MediaLibrary reference, including disabled libraries; disabling retains graph validation. Unreferenced removal succeeds only after checked atomic activation and refreshes the Active list/counts. Removed-root content and historical snapshots remain untouched, failures retain the configured entry, and unknown results are not replayed. |
| AC-6 | Explicit zero-mutation Connection/Read checks show current/bounded evidence, provider-safe errors and recovery; no read check claims write capability and no write probe appears in this Slice. |
| AC-7 | API and Web share permissions, application behavior, redaction, audit, lifecycle and error/recovery semantics; existing V1/V2 journeys and adapters remain green. |
| AC-8 | The supplied reference is committed unchanged and available in another checkout. Controlled screenshots at `1536 x 1024` with drawer step 1 open and closed, plus narrow-screen/keyboard/focus evidence, demonstrate the specified hierarchy, search slot, table/actions and drawer regions. The no-notes override applies; pixel equality and sample data are not acceptance criteria. |
| AC-9 | Final Base..Head evidence covers focused and full regression, browser journeys, typecheck/lint/format/build, governance, secret/private-file audit, FFmpeg/FFprobe exclusion and any configuration/packaging gates material to changed persistence or API composition. |

## Final Validation Expectations

This Slice crosses Active configuration, RBAC, credentials/redaction, concurrency, API and Web, so
Tasks touching those boundaries require the workflow's T4 validation level. B assigns each Task's
level from actual risk; the Slice gate normally includes:

- focused Python tests for provider validation, redaction, references, exact Active concurrency,
  checked read evidence, error categories and zero Storage mutation; prove that activation retains
  required offline strategy/destination calculations without creating media-processing work;
- removal regressions for enabled and disabled dependents, stale confirmation, successful checked
  publication and refreshed inventory, failed validation/evidence/persistence/runtime binding,
  unchanged historical snapshots and physical contents, and unknown-outcome verification;
- focused Web entity/API/component tests for typed projections, form transitions, filtering,
  error/recovery, accessible menus/drawer focus and provider-specific fields;
- Playwright journeys for authenticated success, Add/Edit/copy/enable/disable/remove, referenced
  blocking including disabled dependents, stale/failed activation, read-check failure and
  setup/unavailable handoff; cover shared top-bar search ownership, row action placement and drawer
  closed-by-default, step-1 field order, step navigation and footer accessibility;
- controlled fake/local Storage services and temporary test roots only; no production SMB/OpenList/
  S3/TMDB service, credential or user media;
- normal Python regression, Web tests, typecheck/lint/format/build, `git diff --check`, governance,
  private/config audit and FFmpeg/FFprobe exclusion checks; packaging/migration/release smoke only
  where the actual implementation changes those boundaries.

Visual evidence uses the unchanged committed `docs/pics/储存管理.png` as structural/design-intent
reference at `1536 x 1024`, subject to the explicit no-notes override and Reference Composition and
Interaction above. Verify that the reference is present in the reviewed Git manifest.
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

## Closure Packet

Not submitted. B records factual implementation and validation evidence here when the Required
Outcomes are satisfied, following the development workflow.

## A Final Review

Not performed. A reviews the complete immutable Base..Implementation Head range after B submits
the Closure Packet; this planning checkpoint does not declare any implementation outcome complete.
