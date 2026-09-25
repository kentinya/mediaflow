# Slice 38 — MediaLibrary Files Workspace and Route Separation

This is the A-owned Contract for browsing and maintaining files in configured MediaLibraries using
the approved reference, while preserving and extending the closed Slice 37 ResourceLibrary Files
journey with page-local library configuration editing.

```text
Slice ID: 38
Name: MediaLibrary Files Workspace and Route Separation
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 9e801ae4485bc95d714a8902bf45bf37896fbc2a
Implementation Head: 7d4503e45dc3aa79628ed0d98e887167e1e7c529
Contract Revision: 2026-09-25 A scope expansion — page-local ResourceLibrary/MediaLibrary editing
```

Slice 37 remains `PASS / CLOSED`. Its complete Contract, Closure Packet and A Final Review remain
in Git at `9e801ae4485bc95d714a8902bf45bf37896fbc2a:SLICE.md`, with its closure recorded in
`docs/progress.md`. This Slice does not reopen that implementation or rewrite history. The Base is
immutable. The 2026-09-24 Closure Packet through the recorded Implementation Head remains historical
evidence, but A did not perform Final Review before the user authorized this material scope
expansion. The Slice therefore returns to `ACTIVE`. B may plan the focused editing Task only after
this revised Contract and its ACTIVE Roadmap row are committed.

## User Goal

An authorized operator selects, adds or edits a MediaLibrary, browses actual files below its
configured root, performs ordinary bounded file maintenance, and understands each result and safe
recovery action. The separate Files page retains the complete ResourceLibrary journey, including
Organize, and gains the same direct edit-and-activate configuration experience.

MediaLibrary remains the configured destination used by Classification and Organize. Its browser
shows actual Storage entries, including externally created files, directories and sidecars, whether
or not MediaFlow previously organized or indexed them.

## A Scope Decisions

- Replace the current V2 Library landing content with the MediaLibrary file-management journey.
- Files moves to `/ui-v2/resourcelib/files`; MediaLibrary uses `/ui-v2/medialib/files`.
- Retire `/ui-v2/library/files` and `/ui-v2/library` as supported routes. No compatibility aliases
  or automatic redirects are part of this Contract. Visits reach bounded unavailable-route recovery
  with explicit links to the two supported pages and start no work.
- The visual reference is [媒体库页.png](docs/pics/媒体库页.png), interpreted by
  [the MediaLibrary visual specification](docs/media-library-page-visual-spec.md).
- The user's explicit correction overrides the picture: the new MediaLibrary page has **no card
  file-count/capacity statistics and no file thumbnails**. Do not show `未统计` or other statistics
  placeholders, collect full-library totals, or fetch/generate thumbnails. List/grid entries use
  type icons. Per-entry size, selected-item count/known size and bounded command impact/progress
  remain in scope as file-operation facts.
- MediaLibrary offers the currently delivered Slice 37 common file commands without media Organize
  entry points or requests. Browser Upload/Download remains excluded.
- The presentation exclusions apply to the new MediaLibrary page; they do not authorize unrelated
  changes to the existing ResourceLibrary Files body or shared shell.

## Current A Scope Revision — Unified Library Context Presentation

The Files and MediaLibrary browse pages now use one shared presentation rule for library selection.
This is a focused A-owned correction to page presentation and does not change backend authority,
configuration schema, Storage binding, file commands or safety rules.

- Library cards show only the library icon, library `name`, selection state and independent action
  menu. Cards do not show Storage, Storage ID, root path, file counts, capacity or statistics.
- The selected-library context immediately below the cards shows only truthful enabled state
  (`已启用`) and exact configured root path (`路径: /...`; root is `/`). The name is already on the
  selected card and is not repeated in this context.
- The same composition applies to `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files`, for
  single- and multi-library states. Switching cards updates the context without stale facts.
- Storage remains visible in configuration input and actionable setup/failure recovery, including
  the Add drawer's `存储位置` step, but not in the normal browse-page card or context.
- Disabled libraries remain hidden from browse selection; re-enabling continues through configuration.

This revision supersedes only the earlier card-level Storage/root presentation wording. The Add
drawer and all existing file facts, commands, Organize continuity and safety invariants remain in
force.

## Current A Scope Revision — Unified Single-Entry Command Menus

The Files and MediaLibrary browse pages now use one command-entry rule for individual entries. This
is a focused presentation and interaction correction; it does not change command APIs, permissions,
Storage capability checks, stale evidence, OrganizerExecutor mutation or batch actions.

- Both browse tables remove the `操作` column. The visible columns are exactly
  `选择 | 名称 | 类型 | 大小 | 修改时间`.
- A right-click, Context Menu key or `Shift+F10` on an eligible entry opens the controlled single-entry
  menu. The menu keeps the existing capability/RBAC filtering and confirmation dialogs.
- Folder entries keep `打开`, `重命名`, `复制`, `移动` and `删除` in the menu. A left click on a
  folder's name, icon or non-checkbox row area opens it directly; there is no duplicate inline
  `打开` button. The root remains protected from rename/delete.
- File entries keep supported `打开/编辑`, `重命名`, `复制`, `移动` and `删除`; ResourceLibrary
  entries may also expose `整理`, while MediaLibrary entries never expose Organize.
- Batch selection bars and their bounded batch commands remain unchanged. Moving single-entry
  commands to the context menu does not create new batch semantics or bypass authorization.
- Context menus support Escape/outside click dismissal, keyboard focus return, accessible names and
  usable narrow-screen behavior. Viewing, selecting or opening a menu never submits a mutation.

This revision changes only the entry surface for already-delivered commands. It does not authorize
new operations, arbitrary editing, upload/download, cross-kind transfer or backend fallback.

## Current A Scope Revision — Page-local Library Editing and Activation

The selected ResourceLibrary or MediaLibrary card's configuration menu adds an Edit action beside
the existing removal action. This is a focused completion of the page-local library-management
journey and does not turn either browse page into a general configuration editor.

- Edit opens the same task-oriented `基本信息 → 存储位置 → 确认` composition prefilled from the
  exact current Active object. The stable library ID is visible and read-only; changing an ID is a
  migration, not an edit.
- The editable fields are name, enabled state, existing enabled Storage binding and safe
  Storage-relative root (`storagePath` for ResourceLibrary, `rootPath` for MediaLibrary). Existing
  object fields outside this focused form are preserved and are never reset to creation defaults.
- Opening the form performs zero mutation. Save is bound internally to the exact Active revision
  read for the form, composes a successor, validates the complete dependency graph, runs applicable
  read-only checked evidence, prepares runtime binding and atomically activates only on full
  success. The operator does not handle revision IDs or perform a separate Activate step.
- A stale writer, invalid field/path, unavailable Storage/root, dependency failure, denied
  permission, failed evidence, persistence error or runtime-load failure leaves the prior Active
  and current Storage contents authoritative. Correctable input stays in the form; unknown outcomes
  are not automatically retried.
- A successful enabled edit refreshes the exact card and runtime browse authority. A name-only edit
  preserves a still-valid directory context; a Storage/root change returns that library to its root
  before reading. A successful disable hides the library from browse selection and provides the
  existing configuration recovery handoff. Graph validation may block disabling referenced
  libraries.
- Editing Storage/root changes configuration only. It never moves, copies, renames, creates or
  deletes the old or new root or any media content. Existing admitted work remains pinned to its
  original immutable configuration snapshot.

This revision authorizes only focused editing of existing ResourceLibrary and MediaLibrary objects.
ID rename/migration, bulk editing, editing other configuration-object fields, automatic root-content
migration and general Configuration-page redesign remain outside this Slice.

## Baseline and Requirements

At Base, the V2 Library landing links to ResourceLibrary Files, Scan and Preview; it is not a
MediaLibrary browser. The browser, direct commands, transfer evidence and durable execution currently
resolve ResourceLibrary authority. MediaLibrary configuration and Storage adapters already exist.
Relabelling the page or passing a media ID as a resource ID cannot deliver this Slice.

Applicable requirements include `REQ-LIB-002/003/004/005`, `REQ-STO-*`, `REQ-CONFIG-*`, `REQ-SAFE-*`,
`UX-001/002/003/004/007/009/010`, `V2-UX-*`, `V2-AUTH-*`, `V2-SAFE-001`,
`V2-FILES-002/003/004` for retained Files behavior and `V2-MEDIALIB-001/002/003/004`.
The canonical MediaLibrary definition and final destination composition remain unchanged. Product
and architecture documents distinguish the delivered route/browse/command baseline from the active
page-local editing target.

## Operator Journey and UX Constraints

| Stage | Required experience |
|---|---|
| Entry | Shared sidebar `媒体库` or MediaLibrary deep link; `文件` selects the separate ResourceLibrary route. Authentication continuation preserves a valid page and bounded directory context. |
| Visible state | Shared library cards with name and selection; selected-library context with enabled state and exact configured path (no Storage in normal browse presentation); lazy directory tree; exact relative breadcrumbs; live rows; list/grid; selection; bounded paging; permissions and read failures. |
| Action | Select a library, navigate, search within the existing bounded browser semantics, refresh, select entries, add/edit/remove a library configuration, create folder/text, rename, copy, move, delete or edit supported text. |
| Success | A created or edited enabled library is actually Active and browseable; known file-command success is recorded per item and reflected in a fresh live listing. Long work has durable Task progress and supported lifecycle actions in Web. |
| Failure | Missing Active, missing/disabled library, stale edit authority, invalid path/name, denied permission, unavailable Storage, unsupported capability, stale evidence, conflict, invalid configuration and partial/uncertain mutation identify the affected scope and known effects. |
| Recovery | Follow existing setup/configuration; retain and correct create/edit input; refresh a stale edit before resubmitting; select another library/destination; return to root; refresh/revalidate; inspect durable per-item outcomes and use only backend-advertised safe continuation. |

Ordinary operations do not require raw tokens, revision IDs, Task IDs or evidence copying. Add and
Edit drawers open only on explicit intent and retain correctable input after failure. Navigation or
closing a dialog never implies cancellation/rollback of admitted work. Keyboard use, focus return,
accessible names and usable narrow-screen layouts are required.

## Required Outcomes

### RO-1 — Separate navigation and complete Files continuity

Both new routes, sidebar state, titles, shell search ownership, Dashboard/Operations entry links,
safe authentication continuation and deep links agree on page identity. Internal links stop emitting
retired addresses. Files-originated Organize and return links preserve the ResourceLibrary and exact
relative directory at the new address, including pre-existing durable intent/preview/execution
context where applicable.

Retire the old Library landing body and dedicated navigation/tests as appropriate while retaining
shared Scan, Preview, Operations, configuration and FileIndex application capabilities. No other V2
journey or V1 `/ui` is retired. Existing ResourceLibrary API semantics remain compatible.

### RO-2 — Reference-aligned MediaLibrary presentation

Deliver the image's hierarchy inside the existing shared shell: title/subtitle/Add button, library
cards, directory pane, breadcrumb/refresh/view toolbar, selection action bar above the file list,
six-column table, paging and right-side three-step drawer. Columns are
`选择 | 名称 | 类型 | 大小 | 修改时间`. List/grid use type icons. Library cards and
the selected-library context follow the shared Files presentation: cards show only name/selection
and context shows only enabled state/path. Storage, card statistics, capacity, statistics
placeholders, thumbnails, recognition results and organize-status presentation are absent from the
normal browse page. Individual commands are entered through the controlled context menu; batch
commands remain in the selection bar.
No `整理` or `批量整理` page command appears.

The existing shared sidebar `整理规则` remains. Removing the Organize UI does not remove
OrganizerExecutor from direct file management.

### RO-3 — Live MediaLibrary-scoped browsing

The server resolves an enabled MediaLibrary from the exact Active snapshot, verifies its enabled
Storage binding and confines reads to its root. Requests carry a media-library ID and relative path;
browser-supplied Storage/root paths are not authority. Rows come from live Storage without FileIndex
membership, Result history, recognition or metadata dependencies.

Library selection, lazy navigation, bounded search, deterministic paging and refresh work. Retain
existing bounded search/cursor semantics; do not invent recursive global search, exact full totals
or unsupported arbitrary-page navigation. Exact path identity, including boundary whitespace,
survives projection and navigation. Refresh reconciles stale directory memory and selection while
preserving a still-valid location. Missing paths offer root/read recovery without trimmed-path retry.

### RO-4 — Add, edit and remove MediaLibrary configuration

The page-local Add/Edit drawer offers `基本信息 → 存储位置 → 确认`: name,
immutable-on-creation ID,
enabled state, existing Storage and safe Storage-relative root. API and Web enforce the image's
lowercase-letter/digit/hyphen ID rule. Existing MediaLibrary root validation remains authoritative;
the form does not accept arbitrary host paths or silently create a missing root.

Save composes the candidate into the save-time Active document and performs full configuration/
reference validation, applicable read-only Storage/destination checks, checked activation and runtime
binding. Only complete success publishes an immutable successor. Invalid/duplicate input, missing
root/Storage, concurrent activation, reference and runtime-load failures preserve prior Active
authority and correctable input. Edits replace only the selected immutable-ID object while
preserving every field outside the focused form, bind to the exact Active form snapshot and reject
stale writers. New or edited enabled libraries are immediately selectable; disabled libraries are
saved truthfully but hidden from browsing, with an explicit existing Web configuration handoff for
re-enabling them.

The selected card's configuration-removal action confirms intent, reports blocking references and
uses the same managed authority. Removing configuration never deletes the library root or files.
Referenced libraries cannot be disabled/removed by bypassing graph validation. ID migration,
editing fields outside this focused form and new automatic-directory-creation policy semantics are
outside this Slice.

### RO-5 — Bounded common file maintenance

Offer Create Folder, Create supported Text File, single-item Rename, bounded supported text
Open/Edit/Save, Delete, Copy and Move. File/directory selection and bounded batch/recursive actions
apply where already meaningful in Slice 37. Multi-selection does not imply batch Rename or arbitrary
media editing. Text type/size and provider capability limits remain honest in Web and API.

Copy/Move destinations are the current or another enabled MediaLibrary, including different supported
Storages. Resolve and confine both endpoints independently. Files keeps its existing ResourceLibrary
destination semantics; ordinary cross-kind transfers are deferred. Detect physical self/ancestor
overlap through different library aliases using resolved Storage identity and paths, not just IDs.

Conflicts default to no overwrite. Retain actually supported per-command choices, including transfer
fail/skip/keep-both; no new transfer Replace mode. Delete, supported text Save and any already-supported
explicit replacement retain their distinct intent and current-state validation. Protect library
roots; maintain only selected interior files/directories.

### RO-6 — Durable results and recovery

Long/batch work uses the existing Task/Worker lifecycle with independent item progress, known effects,
results and recovery. Operators can follow progress, revisit work through Operations and use
pause/resume/cancel only when advertised by the backend. Refresh/reconnect never resubmits a mutation.
Same-Storage capability semantics and explicit cross-Storage Copy/verify/Delete-source remain intact;
failed verification preserves source data, and partial/uncertain effects are visible without replay.

Task reconstruction, evidence, scopes, permissions and audit retain library kind and pinned snapshot.
Old ResourceLibrary tasks/results and Organize records remain readable and safely resumable under
their existing rules. Media work cannot be reconstructed as resource work because IDs match. Existing
bounded FileIndex reconciliation may remain after known outcomes but never authorizes/replays a
Storage command.

### RO-7 — Shared mechanisms with independent library authority

Reuse the shell, suitable browse/action presentation, Storage, managed configuration, direct-command
safety and OrganizerExecutor/Task mechanisms. Each page owns its library selection, cache/navigation
state, form and allowed actions. Shared changes cannot leak MediaLibrary restrictions into Files.

Backend lookup, cursors/evidence, manifests, execution/recovery and permission checks distinguish
library kind. Browser cache and continuation distinguish kind, library and path. Equal IDs or
overlapping roots do not make library types interchangeable. Add media-scoped
`/api/v1/media-libraries/...` surfaces using the same application behavior as Web; preserve
resource-scoped API contracts. Only narrowly necessary persistence evolution is in scope, with
migration and recovery evidence when required.

### RO-8 — Demonstrated integration and regression protection

Application/API/Web/browser coverage proves the complete MediaLibrary vertical and migrated Files
journey. Reference screenshots prove the hierarchy with the authorized omissions. Tests cover
failures/recovery and zero-side-effect reads, not just controls or isolated services. Closure
documents truthfully distinguish delivery, deferrals and inherited residual risks.

### RO-9 — Symmetric ResourceLibrary and MediaLibrary configuration editing

Both `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files` expose Edit from the selected card's
configuration menu. The form is prefilled from an exact bounded Active projection, shows ID as
read-only, and edits only name, enabled state, Storage and the kind-specific relative root.

Web and API use kind-specific endpoints backed by the same application lifecycle: exact-Active
optimistic concurrency, merge-without-field-loss, complete validation, applicable read-only
evidence, prepared runtime binding and atomic activation. A successful edit updates the selected
card/runtime truth without requiring a second Activate action. Failure preserves the old Active,
Storage contents and correctable input with an actionable recovery. Resource and media IDs, routes,
cache keys and API payloads cannot cross kinds even when IDs are equal.

## Required Surfaces

- `/ui-v2/medialib/files`, library-relative deep links, common command dialogs and Add/Edit drawer.
- `/ui-v2/resourcelib/files` with complete Slice 37 functionality and Organize return context.
- Shared navigation/search/auth continuation and bounded retired-route recovery.
- ResourceLibrary and MediaLibrary page-local configuration edit projections/mutations using
  checked activation, plus existing MediaLibrary list/browse/save/removal and scoped command APIs.
- Existing Task/Operations progress, item outcomes and supported lifecycle/recovery for media work.
- Existing configuration handoff for setup, unavailable bindings, disabled libraries and references.
- Automated tests and controlled screenshots; no new CLI journey is required.

## Safety and Correctness Invariants

1. Browse, selection, refresh, drawer inspection, configuration checks and operation impact perform
   zero Storage mutation. Reads create no processing work and invoke no metadata Provider.
2. All Storage access uses its interfaces; only OrganizerExecutor mutates, including direct writes.
3. Backend RBAC, memory-only browser authentication, redaction, exact Active authority and immutable
   pinning remain mandatory. New activation cannot silently rebind admitted work.
4. Resolve/confine both endpoints on the server. Protect library/Storage roots, reject escapes,
   unsupported symlinks and aliased self/descendant transfers under existing provider rules.
5. Revalidate capabilities, scope and current evidence; retain concurrency fencing and conflict
   protection. Never silently overwrite/delete, fall back to another operation or mutate a root.
6. Copy/Move bounds are selection/entry count, depth, safe paths and bounded control-plane evidence;
   aggregate media bytes remain impact/progress facts, not admission ceilings. Delete/text retain
   their existing separate bounds.
7. Failed cross-Storage verification preserves the source. Completed siblings/uncertain effects
   are never automatically replayed; durable state and safe next actions remain per item.
8. MediaLibrary maintenance does not run Scanner, Parser, Recognition, Metadata, Naming,
   Classification or media Organize Preview. Existing source Organize retains RecognitionType C
   identity when reusing A policies and exact final destination composition.
9. No stream decoding, FFmpeg/FFprobe, thumbnails or full-library statistics are introduced.
   Per-file metadata reads and bounded command impact remain allowed.
10. Library edit reads and checks perform zero Storage mutation. Edit preserves the stable library
    ID and all unexposed object fields, uses optimistic concurrency and bounded secret-free
    Before/After audit, and cannot silently migrate root contents or rebind already admitted work.

The accepted narrow Local directory replacement/inode-reuse race remains inherited residual risk,
with existing prevention/recovery guidance. This Slice does not claim to fix it or weaken checks.

## Explicitly Deferred / Excluded

- Card statistics/capacity/placeholders; thumbnail/cover/preview fetching or generation; video
  frame extraction. These are explicitly removed from this product scope, not hidden follow-up
  Tasks or required future enhancements.
- MediaLibrary Scan/Preview/Organize, recognition/status columns, metadata catalog/poster wall,
  playback, stream inspection and FileIndex-driven physical membership.
- Browser Upload/Download, arbitrary binary/image/video editing, batch Rename, unbounded
  recursion/global search and new transfer overwrite/Replace.
- Ordinary ResourceLibrary↔MediaLibrary transfers; existing policy-driven source Organize to
  MediaLibrary remains supported.
- New providers/capabilities or identity system, library ID rename/migration, automatic movement or
  copying of contents after a Storage/root edit, bulk library editing, editing fields outside the
  focused page-local form, broad configuration migration, new automatic
  directory-creation policy behavior, V1 cutover, generic workflow/persistence redesign, universal
  rollback and automatic uncertain replay.
- Changes to the user's dirty `docs/pics/文件页.png`, unrelated shell/product redesign, and any
  Files presentation change beyond the explicitly required shared library-card/context parity and
  single-entry command-menu parity.

## Slice Acceptance Criteria

| ID | Acceptance |
|---|---|
| AC-1 | Both new routes support direct/sidebar/auth continuation; retired routes offer bounded recovery, and internal links no longer emit them. |
| AC-2 | Reference hierarchy and drawer work without card statistics/placeholders or thumbnails; normal entry keeps the drawer closed. |
| AC-3 | Live browse covers empty/multi-page libraries, exact whitespace paths, missing current directory and refresh of externally removed directories without fabricated rows or FileIndex dependency. |
| AC-4 | Add/Edit succeeds only after actual activation; invalid/duplicate/stale input, Storage/root/reference and concurrent activation failures preserve Active with recovery. Disabled-save and safe configuration removal are explicit. |
| AC-5 | Each common command completes in Web/API with matching permissions/results, covering single/multi-item, directories, conflicts, stale, denied, read-only and unsupported-provider cases. |
| AC-6 | Media transfers work within/between libraries, including cross-Storage verification, independent partial results, durable revisit and supported lifecycle continuation without replay. |
| AC-7 | Same-ID libraries, overlapping roots, cursor/evidence reuse, snapshot changes and Worker reconstruction cannot cross authority; pre-existing ResourceLibrary durable work remains compatible. |
| AC-8 | Files retains add/remove, browse/search/refresh, direct commands, single/batch Organize, policy binding and return context; other V2/V1 journeys remain functional. |
| AC-9 | Safety invariants hold; final evidence and CURRENT documentation cover all vertical outcomes without claiming excluded capabilities. |
| AC-10 | ResourceLibrary and MediaLibrary Edit are prefilled, ID-immutable, field-preserving and kind-separated; success atomically activates and refreshes truthful browse state, while failure retains input, prior Active and zero Storage-content mutation. |

## Final Validation Expectations

B assigns Task Difficulty/Test Level from actual risk. Active configuration, RBAC, mutation,
persisted scope and Worker changes require T4 where the workflow specifies it; this activation does
not assign implementation Tasks or classify their work as T0.

Before a Closure Packet, run Slice-final Python regression, Web unit/component regression,
typecheck/lint/format/build and full browser journeys, including migrated Files and MediaLibrary
success/failure/recovery. Complete normal Python quality/dependency/FFmpeg-exclusion and governance
checks. Run packaging and installed-artifact/Docker release-security and transfer smoke gates
material to API composition, immutable bindings and resident Worker execution; include upgrade/
recovery rehearsal if persisted schemas change. Use fake/local services and temporary media, never
production credentials/services or user media. Record actual totals/skips/unavailable gates.

Capture controlled `1536 x 1024` screenshots with Add and Edit step 1 open and closed, plus usable
narrow-screen evidence. The exclusions deliberately differ from the image; structural alignment and
functioning controls determine acceptance, not zero pixel differences. Files regression covers the
new address without redesigning its body.

Inspect the full commit manifest/private files and `git diff --check`. Preserve the pre-existing
dirty Files image. Include the supplied MediaLibrary image unchanged as the canonical reference.

## Delegated Factual Updates and Stop Rule

B may update Implementation Head and submit factual checkpoint, outcome status, test and risk
evidence in the Closure Packet. B cannot change Base/boundaries/acceptance or close the Slice. Once
Required Outcomes are satisfied, stop creating Tasks and submit the packet for A's
Base..Implementation Head review under the development workflow.

## Current B Closure Packet — Task 38.8

```text
Slice: 38 — MediaLibrary Files Workspace and Route Separation
Base SHA: 9e801ae4485bc95d714a8902bf45bf37896fbc2a
Head SHA: 7d4503e45dc3aa79628ed0d98e887167e1e7c529

Required Outcomes:
- RO-1 COMPLETE — separate ResourceLibrary/MediaLibrary routes and Files continuity remain green.
- RO-2 COMPLETE — reference-aligned MediaLibrary hierarchy and omissions remain green.
- RO-3 COMPLETE — live bounded MediaLibrary browsing and path recovery remain green.
- RO-4 COMPLETE — MediaLibrary Add/Edit/Remove uses checked Active activation and recovery.
- RO-5 COMPLETE — bounded common file maintenance and transfer behavior remain green.
- RO-6 COMPLETE — durable per-item outcomes and supported recovery remain green.
- RO-7 COMPLETE — library kind, IDs, roots, snapshots and Worker authority remain separated.
- RO-8 COMPLETE — application/API/Web/browser integration and safety evidence are complete.
- RO-9 COMPLETE — symmetric exact-Active ResourceLibrary/MediaLibrary editing is delivered.

Required Surfaces:
- `/ui-v2/medialib/files` and `/ui-v2/resourcelib/files` with Add/Edit/remove and file journeys COMPLETE.
- Shared navigation/search/auth continuation and retired-route recovery COMPLETE.
- Kind-specific edit projections and PUT mutations with checked activation COMPLETE.
- Operations progress, item outcomes, lifecycle/recovery and configuration handoff COMPLETE.
- Automated regression, browser journeys and controlled edit screenshots COMPLETE.

Implemented:
- Task 38.8 added immutable-ID ResourceLibrary and MediaLibrary page-local edit projections and
  atomic PUT activation, preserving unexposed fields and exact Active concurrency.
- Edit projections now carry enabled Storage choices from the same verified Active snapshot;
  malformed or unrepresentable bindings fail closed with visible recovery.
- Web drawers retain correctable input, avoid automatic replay, reconcile browse state, expose
  disabled-library configuration handoff and restore keyboard focus after known success.
- API, component, browser and fake/local-server evidence covers success, stale/failure recovery,
  Storage authority, no replay, RBAC, zero Storage-content mutation and unchanged Remove behavior.

Tasks completed:
- 38.1 Route separation and MediaLibrary Files shell
- 38.2 Live MediaLibrary browsing and configuration lifecycle
- 38.3 Bounded MediaLibrary direct maintenance commands
- 38.4 MediaLibrary Copy/Move transfer and recovery
- 38.5 Slice integration validation and Closure Packet
- 38.6 Files/MediaLibrary unified library-selection context presentation
- 38.7 Files/MediaLibrary unified single-entry menus and folder activation
- 38.8 ResourceLibrary/MediaLibrary page-local edit and atomic activation

Final Tests:
- `.venv/bin/python -m unittest discover -s tests` — PASS, 1795 tests, 7 skipped.
- `npm --prefix web run test -- --run` — PASS, 43 files / 611 tests.
- `npm --prefix web run test:e2e` — PASS, 181 tests.
- Web typecheck, lint, format check and build — PASS; build retained existing chunk-size warning.
- `python3 scripts/check_governance.py`, `git diff --check`, compileall, Ruff check/format — PASS.
- Docker release-security smoke — PASS; transfer-impact smoke — PASS with bounded 22,548,578,304-byte
  impact evidence and fail-closed depth/entry/escape probes.
- Wheel install/configuration/backup/migration/restore/verify smoke — PASS; no schema migration required.
- FFmpeg/FFprobe exclusion and private-file/config audit — PASS; `config/alist.json` remains ignored
  and the pre-existing `docs/pics/文件页.png` modification remains outside the checkpoint.
- Controlled Add/Edit screenshots and narrow-screen/focus browser evidence — PASS.

Safety Evidence:
- Edit reads, validation, evidence and activation use the managed exact Active snapshot and perform
  zero Storage-content mutations; no Scanner, Task, Provider, Metadata or OrganizerExecutor work is
  started.
- Stable IDs and unexposed fields are preserved; stale revision/digest writers fail closed before
  publication, and bounded secret-free audit/runtime binding remain on the existing activation path.
- Web/API RBAC and kind-specific namespaces remain aligned; unknown results are not retried and
  disabled libraries never delete or migrate Storage content.

Known Non-blocking Issues:
- Existing unclosed-SQLite `ResourceWarning` noise in the Python regression remains inherited.
- Existing Web production chunk-size warning remains non-blocking.
- Accepted narrow Local directory replacement/inode-reuse race remains outside this Slice.

Explicitly Deferred:
- Maintained exactly as listed in `Explicitly Deferred / Excluded`, including thumbnails/statistics,
  MediaLibrary Scan/Preview/Organize, Upload/Download, cross-kind transfers and transfer Replace.

Documentation Reconciliation Needed:
- A should reconcile the canonical Product Experience, Requirements, Architecture and Roadmap text
  that still describes page-local ResourceLibrary/MediaLibrary editing as TARGET/planned, and record
  the final Slice 38 closure ledger.

Decision: SLICE READY FOR A REVIEW
```

## Historical Closure Packet — superseded by 2026-09-25 A scope expansion

Slice: 38 — MediaLibrary Files Workspace and Route Separation
Base SHA: 9e801ae4485bc95d714a8902bf45bf37896fbc2a
Head SHA: 1ae0531212c1c5c585cc2970c03f9996c1eba949

Required Outcomes:
- RO-1 COMPLETE — route separation, navigation/auth continuation and ResourceLibrary Files
  continuity remain covered; the two browse routes now share one selector/context composition.
- RO-2 COMPLETE — MediaLibrary hierarchy, five-column live table, Add drawer and unified cards/
  selected context are present; both browse tables now use the required five physical columns and
  controlled single-entry menus, while Storage facts, statistics, thumbnails and MediaLibrary
  Organize controls remain absent from the normal browse presentation.
- RO-3 COMPLETE — live, bounded MediaLibrary browsing, exact paths, paging, refresh and
  missing-directory recovery are covered by application and browser tests.
- RO-4 COMPLETE — checked Active configuration save/removal, disabled truthfulness and failure
  recovery are covered by API/Web/browser tests.
- RO-5 COMPLETE — bounded common commands and same/cross-Storage Copy/Move preserve authority,
  conflict and capability rules.
- RO-6 COMPLETE — durable per-item transfer outcomes, revisit and supported continuation are
  covered without mutation replay.
- RO-7 COMPLETE — library kind, IDs, roots, snapshots, evidence and Worker reconstruction remain
  authority-separated while ResourceLibrary work remains compatible.
- RO-8 COMPLETE — vertical application/API/Web/browser and safety evidence is recorded below.

Required Surfaces:
- `/ui-v2/medialib/files`, library-relative links, command dialogs and Add drawer COMPLETE.
- `/ui-v2/resourcelib/files` and Organize return context COMPLETE.
- Shared navigation/search/auth and retired-route recovery COMPLETE.
- MediaLibrary browse/configuration and scoped command APIs COMPLETE.
- Operations progress, item outcomes and supported lifecycle/recovery COMPLETE.
- Configuration handoff for setup, unavailable bindings, disabled libraries and references COMPLETE.
- Automated tests and controlled screenshots COMPLETE.

Implemented:
- Tasks 38.1–38.4 delivered route separation, live browsing, configuration lifecycle, bounded
  commands and durable MediaLibrary transfers; Task 38.5 completed Slice-level validation.
- Task 38.6 unified ResourceLibrary and MediaLibrary browse cards and selected-library context while
  preserving route-specific commands, configuration and recovery behavior.
- Task 38.7 unified five-column list/grid entry interaction, controlled context menus and direct
  folder activation while preserving command dialogs, batch behavior and backend authority.
- The pre-existing dirty `docs/pics/文件页.png` remains outside every reviewed checkpoint; the
  supplied `docs/pics/媒体库页.png` is unchanged in Base..Head.

Tasks completed:
- 38.1 Route separation and MediaLibrary Files shell
- 38.2 Live MediaLibrary browsing and configuration lifecycle
- 38.3 Bounded MediaLibrary direct maintenance commands
- 38.4 MediaLibrary Copy/Move transfer and recovery
- 38.5 Slice integration validation and Closure Packet
- 38.6 Files/MediaLibrary unified library-selection context presentation
- 38.7 Files/MediaLibrary unified single-entry menus and folder activation

Final Tests:
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m unittest discover -s tests` — PASS, 1791 tests, 7 skipped.
- `npm --prefix web run test -- --run` — PASS, 43 files / 603 tests.
- `npm --prefix web run test:e2e` — PASS, 170 tests.
- `npm --prefix web run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts`
  — PASS, 60 tests; the two folder-keyboard blocker regressions also passed independently.
- Typecheck, lint, format check, build, Ruff format/check, compileall, pip check and both
  configuration validations — PASS.
- FFmpeg/FFprobe production exclusion audit — PASS, zero hits under `mediaflow` and
  `pyproject.toml`.
- Isolated wheel build/install/configuration and schema-38 backup/migration/restore/verify smoke —
  PASS.
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS, including built V2
  artifact, immutable runtime binding and resident Worker execution.
- `.venv/bin/python scripts/docker_files_transfer_impact_smoke_test.py` — PASS; a sparse
  22,548,578,304-byte selection was admitted as bounded impact evidence while limit/escape probes
  failed closed and no Copy/Move/Delete mutation occurred.
- Controlled MediaLibrary screenshots — PASS: Add closed `1536x1024`, Step 1 open `1536x1024`,
  and narrow Step 1 `760x900`; all generated with the local fake server and visually inspected.
- `git diff --check`, Base..Head manifest, private-file/config audit and reference-image checks —
  PASS; `config/alist.json` and browser outputs remain ignored and no credentials/build artifacts
  are committed.

Safety Evidence:
- Tests cover zero-mutation reads, backend RBAC, exact Active snapshot authority, endpoint
  confinement, root protection, stale/conflict handling, per-item partial outcomes and no replay.
- OrganizerExecutor remains the only Storage mutation boundary; no metadata Provider, Scanner,
  Parser, thumbnails, stream decoding or full-library statistics were introduced.
- Task 38.6 changed only Web presentation/tests and did not change API payloads, Active authority,
  Storage bindings, route parameters or backend mutation behavior.
- Task 38.7 changed only shared Web entry presentation/interaction and tests; menu open/dismiss and
  folder navigation remain zero-mutation, while all commands reuse the existing guarded callbacks.

Known Non-blocking Issues:
- Inherited narrow Local directory replacement/inode-reuse race remains documented residual risk;
  it is outside this Slice and does not weaken current checks.
- The production Web build retains its existing large-chunk warning, and Python regression emits
  existing unclosed-SQLite `ResourceWarning` noise; neither caused a failure or current-journey
  defect in this validation.

Explicitly Deferred:
- Maintained exactly as listed in `Explicitly Deferred / Excluded` above, including thumbnails/
  statistics, MediaLibrary Scan/Preview/Organize, Upload/Download, cross-kind transfers and
  transfer Replace mode.

Documentation Reconciliation Needed:
- After Final Review, A should reconcile Slice 38 in Roadmap/Progress and update canonical product,
  Product Experience and Architecture sections that still label the delivered MediaLibrary route
  as TARGET/planned or describe the pre-correction library context. No Contract or implementation
  change is requested.

Historical Decision: SLICE READY FOR A REVIEW

This packet remains the factual B submission for implementation through
`1ae0531212c1c5c585cc2970c03f9996c1eba949`. It is no longer the current stop-rule decision because
RO-9 and the expanded RO-4/AC-10 are not implemented. A Final Review was not performed before the
scope expansion.

## A Final Review

Reviewed Range: 9e801ae4485bc95d714a8902bf45bf37896fbc2a..7d4503e45dc3aa79628ed0d98e887167e1e7c529
Decision: PASS / CLOSED
P0-P1 Blockers: None.

Closure Reconciliation:
- RO-1 through RO-9 are complete across the two supported Web routes, their shared API/application
  behavior, page-local Add/Edit/Remove configuration journeys, live Storage browsing, bounded direct
  maintenance and transfer recovery.
- Required surfaces are present, including retired-route recovery, Operations durability, kind-specific
  API namespaces, exact-Active editing, controlled screenshots and narrow-screen/focus evidence.
- The zero-mutation analysis/configuration boundaries, OrganizerExecutor-only Storage mutation,
  explicit conflict/destructive intent, immutable snapshot pinning, no automatic uncertain replay,
  library-kind isolation and RecognitionType identity rules remain intact. RecognitionType C remains C
  when A downstream policies are reused.
- The Closure Packet's final regression, browser, quality, packaging, transfer-impact, private-file and
  FFmpeg/FFprobe checks were corroborated by A's governance check, focused activation/edit regressions,
  and the full Python regression (`1795` tests, `7` skipped, `OK`). Existing SQLite ResourceWarning
  noise and the retained Web chunk-size warning remain non-blocking.
- Documentation now records the delivered Slice 38 route, MediaLibrary and symmetric page-local edit
  behavior as CURRENT. The explicitly deferred statistics/thumbnails, MediaLibrary Organize/Scan/
  Preview, browser Upload/Download, cross-kind direct transfers, transfer Replace mode, ID migration,
  broad configuration redesign, V1 cutover, universal rollback and automatic uncertain replay remain
  deferred and are not hidden dependencies.
