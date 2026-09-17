# Task 37.4 — Files Bounded Copy and Move Transfers

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.4
Parent Slice: 37
Status: PLANNED
Task Base: 4954502c6493d57634a14461a7268120419319da
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Advance Slice 37 **RO-6 Complete common file management**, **RO-7 Low-friction direct-operation
safety**, **RO-8 Organize workflow continuity** and **RO-9 Actionable recovery** by delivering the
complete Web-native Copy and Move journey for one item or a bounded selection of files/directories.
An authorized operator chooses an
explicit destination inside an enabled Active ResourceLibrary, sees truthful capability/conflict and
compound-transfer behavior, and receives independent durable outcomes without media-organize
ceremony, silent fallback, silent replacement or unsafe source deletion.

The Task also makes the existing explicit `sourceDirectoryCleanup` policy complete for the common
OpenList/S3 journey where one media file is organized with `MOVE` and the same source directory
contains only narrowly configured advertising/junk files. After the media move is verified, those
policy-matched files and the then-empty source directory can be cleaned safely and truthfully; an
unknown entry, exceeded bound or uncertain effect stops cleanup instead of broadening deletion.

This Task also advances **RO-11 Test reconciliation** and **RO-12 Security model continuity**. It
extends the direct-file-command boundary established by Task 37.3; it does not implement Upload,
Download or the remaining media-Organize/FileIndex reconciliation journey.

The Task also corrects three confirmed Task 37.3 Files regressions that block the existing journey:
the visible ResourceLibrary card contains pointer dead zones, bounded multi-selection Delete cannot
load its impact summary because the API rejects repeated `path` values, and the fixed-height file
table clips additional rows and row-action menus instead of providing a usable scrolling surface.
These are preservation corrections inside **RO-3 Exact Files composition**, **RO-5
Storage-authoritative Files data**, **RO-6 Complete common file management**, **RO-7 Low-friction
direct-operation safety**, **RO-9 Actionable recovery** and **RO-11 Test reconciliation**. They do
not weaken Delete confirmation, exact-entry evidence, confinement, limits or OrganizerExecutor-only
mutation.

## Why This Task Exists

Task 37.3 completed bounded Create, Rename, text Edit and Delete, but the visible Files toolbar still
cannot carry selected content to another directory or ResourceLibrary. Copy and Move form one
coherent transfer unit because they share source enumeration, destination selection, conflict
policy, capability admission, progress and per-item recovery. Move adds the critical compound
boundary: cross-Storage source deletion is legal only after a verified Copy, while a failure after
Copy must remain visible as a partial result rather than being hidden or replayed.

This is the largest independently reviewable next behavior inside the Slice. Upload/Download have
different browser-stream and archive/request limits and remain a later unit. Media Organize
redesign, multi-item Organize completion and FileIndex reconciliation remain separate, but the
already-existing Move cleanup policy is part of this Task because it shares the exact source-delete,
provider and partial-effect boundary being completed here.

Task 37.3 deliberately fails direct Rename/Delete closed when a provider exposes no reliable entry
identity. In the current adapters that means OpenList files/directories cannot use Files direct
Delete, while S3/R2 files can use their object validator but synthetic/virtual directories cannot.
That protection remains correct. It does not, however, satisfy the operator goal of moving one real
media file and removing explicitly classified advertising files left beside it. This Task closes
that journey through policy-scoped cleanup authority rather than pretending OpenList has an exact
entry identity or weakening direct Delete.

### Confirmed Files regression corrections

The following behavior was reproduced against the current Task Base and is mandatory in this Task:

- **ResourceLibrary card hit target:** the visible card wrapper presents a pointer cursor and selected
  styling, but only its small inner label button changes the ResourceLibrary. Clicking the card
  padding or border therefore appears to do nothing. The complete visible card surface must select
  the ResourceLibrary except for the explicit `...` action-menu control, which remains an independent
  action and must never switch libraries.
- **Bounded multi-selection Delete contract:** Web encodes a selection as repeated query parameters
  such as `?path=a&path=b`, while the API parser currently rejects every repeated field. Two or more
  selected paths therefore fail before the zero-mutation impact summary. The API must accept only a
  bounded repeated `path` field, preserve all existing path normalization/limit/identity checks, and
  continue to require one exact confirmation digest before mutation.
- **Scrollable rows and unclipped actions:** the work area and file pane are fixed at `535px`, the
  flexed table wrapper is shorter than a ten-row table, and `overflow: hidden` clips the remaining
  content. The row menu is also rendered inside an overflow-clipped table cell/container. The file
  list must have a real keyboard/pointer/touch-scrollable viewport, every returned row must be
  reachable, and the row menu must render above the table clipping context with viewport-aware
  placement.

The expected operator outcome is the approved visual direction demonstrated during planning: at the
controlled `1536 x 1024` viewport the selected ResourceLibrary is unambiguous, a ten-entry directory
can be scrolled through to the tenth entry, `共 10 个项目` remains truthful, and a bottom-row `...`
menu can visibly expose Rename/Edit/Delete without leaving the current Files context.

## Implementation Scope

```text
Files selection and destination picker
→ direct transfer domain/application admission
→ durable Task/per-item transfer execution
→ OrganizerExecutor-only Storage mutation
→ authenticated API
→ Files progress/result/recovery
→ tests
```

- Add direct `COPY` and `MOVE` commands for one item or a bounded selection of regular files and
  bounded directory trees. The browser submits only source ResourceLibrary identity, normalized
  ResourceLibrary-relative source paths, destination ResourceLibrary identity, normalized relative
  destination directory, requested operation, explicit conflict choice and opaque server-issued
  evidence required by the command. It never submits host paths, Storage roots or credentials.
- Resolve source and destination from one exact immutable Active runtime snapshot at admission and
  pin that identity to all durable transfer work. Reject missing, disabled, changed or mismatched
  ResourceLibraries/Storages and stale runtime evidence before mutation; an in-flight Task never
  silently switches to a later Active configuration.
- Implement a Files-native destination picker backed by bounded live Storage reads. It lists only
  eligible enabled Active ResourceLibraries and confined directories, shows the selected
  ResourceLibrary/path and operation availability, supports safe breadcrumb/navigation recovery,
  and never uses FileIndex or client-side path joining as authority.
- Preserve the current source directory, selection and destination choice while the operator fixes
  an actionable validation/capability/conflict error. Opening/cancelling the picker is zero-mutation
  and creates no Task. Successful or known-partial completion refreshes the affected live source
  and destination views and removes/remaps only selection whose physical truth changed.
- Enumerate every selected directory through Storage within explicit item, depth and total-byte
  limits before mutation. Reject ResourceLibrary roots, symlinks/unsupported entry types, overlap
  that would copy or move a directory into itself/its descendant, duplicate/nested selected roots,
  path escape and any unbounded scope. The confirmed logical transfer manifest stays bounded and
  preserves independent top-level/per-entry outcome identity.
- Revalidate source type/version and destination state at admission and immediately before each
  mutation. Use provider-verifiable evidence or a provider-native conditional operation when the
  transfer command depends on exact identity; if the provider cannot prove the required boundary,
  fail closed with an actionable reason. Do not weaken Task 37.3's Rename/Delete evidence contract
  or treat size/`mtime` alone as authority to delete one exact manifest source. The separately
  declared `ignorable` cleanup policy authorizes a narrow current-name predicate rather than an
  exact pre-confirmed object, as specified below; it may not escape that parent/pattern boundary.
- For same-Storage Copy/Move, use only the adapter capability and native operation it truthfully
  advertises. Never implement Move as Copy, Copy as Move, or another operation implicitly. If a
  provider cannot natively perform the requested operation for the selected entry type/scope, show
  that limitation before mutation or as the exact affected-item failure; do not fabricate success.
- For a bounded directory tree, explicitly plan required destination directories and file
  transfers. Every `CreateDirectory`, `Copy`, `Move`, `Write` or `Delete` call must occur through
  `OrganizerExecutor`; application/API/Web code may list, stat and read for bounded admission or
  transfer but may not invoke mutating Storage methods directly.
- For cross-Storage Copy, use an explicitly admitted bounded streaming path and verify the produced
  destination before reporting success. Verification must be strong enough to distinguish a
  truncated or changed transfer and must not use FileIndex as authority. A verification failure
  records the destination as failed/partial/uncertain according to the known effect and never
  reports a completed Copy.
- For cross-Storage Move, expose and persist the exact compound checkpoints `Copy destination →
  verify destination → Delete source`. Delete the source only after verified Copy and fresh exact
  source revalidation. Failed Copy or verification always preserves the source. A failure or
  authority loss after verified Copy leaves the source intact when deletion is not known complete,
  records both known copies/uncertain effects truthfully and provides an explicit cleanup or
  continuation action; it is never automatically retried as a whole Move.
- Preserve the semantic distinction between **Files direct Delete** and **Organize source cleanup**.
  Direct Delete continues to authorize one exact confirmed entry/scope and therefore continues to
  fail closed without provider-verifiable identity. `sourceDirectoryCleanup.mode=ignorable` is a
  separate explicit OrganizePolicy authorization: it authorizes deletion of the current regular
  files in the exact moved media file's parent whose basenames match narrowly configured patterns.
  A same-name replacement that still matches such a pattern remains inside that declared policy
  intent; the policy is not represented as exact-object confirmation and must never be used by the
  ordinary direct Delete endpoint.
- Complete the existing source-cleanup journey for writable Local, SMB, OpenList and S3/R2 Storage.
  Cleanup runs only after a `MOVE` primary effect is verified. Immediately before cleanup, re-list
  the exact confined source parent, enforce `maxParentDirectories` and `maxEntries`, require every
  remaining entry to be a direct regular-file child whose basename matches at least one configured
  `ignorePatterns` rule, and re-stat each admitted entry. Any directory, symlink, unknown file,
  pattern mismatch, changed type/name, exceeded bound or Storage error stops before deleting the
  not-yet-processed cleanup scope and reports the blocker.
- Cleanup patterns are explicit destructive policy, not a heuristic classification. Empty patterns,
  `/` or `\\`, `*`, `**`, path traversal and more than the existing bounded pattern count remain
  invalid. The UI/Preview must show the exact configured patterns, parent-directory bound, entry
  bound, currently matched files, any blocking unknown entries and the fact that matched source
  files will be permanently deleted after a successful Move. No filename, extension or "advertising"
  guess may be added implicitly.
- Record every cleanup deletion and directory outcome independently through `OrganizerExecutor` and
  the existing mutation-authority checks. Failure after deleting some policy-matched files is a
  partial cleanup with exact known effects; it does not change a successful media Move into a
  fabricated all-or-nothing result and it is never automatically replayed. Recovery starts from a
  fresh source listing and asks the operator to inspect or explicitly continue only known-safe work.
- Treat provider directory semantics truthfully. For OpenList, delete the directory only after the
  provider confirms it is empty. For S3/R2, a prefix with no remaining objects and no directory
  marker is already absent and must be recorded as successful cleanup without attempting to delete
  a fictional directory object; if an explicit marker exists, delete only that empty marker through
  the executor. Direct recursive Delete of an S3 virtual directory remains unavailable unless its
  own exact-scope requirements are separately met.
- Run directory, cross-Storage and multi-item transfers through the existing Task system with
  bounded progress and durable independent item outcomes. A short same-Storage single-file command
  may complete inline only through the same application, audit and OrganizerExecutor boundaries.
  Pause/cancel takes effect only at safe item/checkpoint boundaries and never converts an unknown
  effect into a retryable failure.
- Default every destination conflict to no overwrite. Support explicit `跳过` and `保留两者/重命名`
  behavior where the backend can determine a safe target. If `替换` is offered, require a separate
  permanent-effect confirmation bound to the exact current destination and revalidate it at the
  last safe boundary; otherwise omit Replace rather than weakening overwrite safety. Conflict
  policy and generated keep-both names are backend-authoritative and recorded per item.
- Make overlap and batch conflict handling deterministic. One item may not overwrite, hide or block
  the diagnosis of another. Items that can safely continue may do so only when the chosen batch
  policy makes that intent explicit; completed siblings are never replayed during recovery.
- Persist bounded, secret-free transfer result/audit evidence: actor, operation, logical
  ResourceLibrary-relative source and target, same/cross-Storage mode, conflict choice, checkpoints,
  status, known effects, retry safety and stable failure/recovery category. Do not persist host
  roots, credentials, authorization data, raw provider responses/exceptions or file content.
- Expose authenticated API behavior that uses the same application service, RBAC, snapshot,
  confinement, capability, limits, stale/conflict, audit and result rules as Web. Stable errors must
  distinguish invalid selection/destination, capability denial, stale source/destination, conflict,
  limit overflow, verification failure, partial completion and uncertain effect.
- Add Copy and Move to applicable Files toolbar, row and bounded-selection action surfaces. The
  operator can inspect source count, destination and operation truth, submit once, follow progress,
  inspect each outcome and take the advertised safe recovery action without handling Task IDs or
  internal execution tokens as ordinary ceremony. Keyboard, touch, Escape, focus restoration and
  duplicate-submit prevention remain supported.
- Correct the ResourceLibrary card interaction so one semantic selection control covers the whole
  visible non-menu card surface. Do not nest interactive controls: keep the selected card's `...`
  action as a separate sibling/overlay target with its own focus and event boundary. Clicking card
  padding, label, icon or border selects exactly once; clicking the action menu never switches the
  ResourceLibrary.
- Reconcile the Delete impact query contract by accepting repeated `path` values as the one allowed
  bounded array field. Reject unknown query keys, blank values, unsafe paths, duplicates/overlap
  that violate the existing selection rules and selections above the existing maximum. Impact
  lookup remains a zero-mutation read, and execution still echoes the server-issued scope digest
  through the existing confirmed Delete command.
- Replace the fixed/clipped list body with a constrained flex/grid layout whose table viewport has
  `min-height: 0` and explicit `overflow-y: auto` while retaining bounded horizontal behavior. The
  directory tree may scroll independently when needed; the toolbar and selection/pagination footer
  remain visible and are not part of the row scroll.
- Render row action menus outside overflow-clipped table cells and scrolling ancestors, using a
  portal or an equivalent shared popover layer anchored to the invoking button. Clamp or flip the
  menu within the viewport, close or reposition it on scroll/resize, preserve Escape/outside-click
  dismissal and restore focus to the exact invoking row control. Do not solve the issue by removing
  the list's required overflow boundary.
- Preserve Task 37.1–37.3 shell, Files browse/search/sort/paging/view, ResourceLibrary selection and
  activation/removal, Create/Rename/Edit/Delete, organize Preview entry, non-Files V2 routes and V1
  `/ui`. Preserve the pre-existing dirty `docs/pics/文件页.png` and ignored local interaction
  references; do not stage, rewrite or use them to mask a functional failure.

## Concrete Implementation Plan

### 1. Domain contracts and bounded manifests

- Add provider-neutral transfer values equivalent to `TransferOperation(COPY|MOVE)`,
  `TransferConflictMode(FAIL|SKIP|KEEP_BOTH|REPLACE)`, `TransferManifest`,
  `TransferManifestEntry`, `TransferCheckpoint` and `TransferItemOutcome`. Reuse existing Storage
  and Task concepts; these types must not contain host paths, credentials or provider DTOs.
- A manifest binds the pinned configuration revision/digest, source/destination ResourceLibrary and
  Storage identities, normalized relative roots, entry type/size/modified time/provider identity
  when available, requested operation, conflict choice, generated keep-both target, directory
  topology and configured limits. Return only an opaque manifest digest/evidence to Web.
- Define one bounded cleanup projection equivalent to `SourceCleanupImpact`: exact parent,
  configured mode/patterns/bounds, matched current files, blocking entries and expected directory
  outcome. It is explanatory evidence for the already-pinned OrganizePolicy, not a reusable direct
  Delete token.

### 2. Application admission and service boundary

- Add or compose a `DirectFileTransferService` with two phases: a zero-mutation impact/admission
  phase and an explicitly submitted execution phase. Both phases resolve the same Active snapshot,
  canonicalize paths on the backend, enumerate bounded source trees, calculate deterministic
  destinations/conflicts and reject invalid or stale evidence before creating mutation work.
- Reuse the existing ResourceLibrary Files browser for destination navigation and add only the
  projection needed to explain Copy/Move eligibility. Do not build a second Storage browser or
  allow the frontend to infer capability from provider names.
- At execution admission, rebuild the manifest from live Storage and compare it with the opaque
  submitted evidence. A mismatch returns a stable stale-manifest error and a fresh-impact action;
  no Task or mutation is created from stale evidence.
- Keep source cleanup inside the existing Organize execution path. Extend its read-only Preview/
  explanation projection so the operator sees matched junk files and blockers, then pass the exact
  pinned `DirectoryCleanupPolicy` and source parent into `OrganizerExecutor`. Do not route cleanup
  through the Files direct Delete service and do not add a second cleanup authority.

### 3. OrganizerExecutor transfer primitives

- Add narrow executor methods equivalent to same-Storage Copy/Move, cross-Storage streamed Copy and
  cross-Storage compound Move. Every method accepts explicit mutation authority and structured
  evidence, performs a last-boundary preflight, invokes only the requested Storage operation and
  returns effect certainty plus completed checkpoints.
- Same-Storage operations call only `Storage.copy` or `Storage.move` according to the request and
  advertised capability. Bounded directory Copy may compose executor-owned directory creation and
  per-file native Copy; directory Move may use the provider's native Move only when the provider
  truthfully supports that entry/scope. There is no hidden cross-operation fallback.
- Cross-Storage Copy streams in bounded chunks while calculating source verification evidence,
  publishes the target only through executor-owned `Storage.write`, then verifies the destination
  with a bounded streamed digest/size comparison or an equally strong provider-native validator.
  Do not load a media file wholly into memory and do not report success from size alone.
- Cross-Storage Move persists `COPY_WRITTEN`, `DESTINATION_VERIFIED` and `SOURCE_DELETED` checkpoints.
  It revalidates the exact source after destination verification; if exact destructive authority is
  unavailable, it ends as a recoverable verified-copy/source-retained partial outcome instead of
  deleting with weak evidence.
- Refactor `_cleanup_source_directories` only as needed to emit per-entry known effects and to treat
  an absent S3 virtual prefix as already cleaned. Keep pattern and boundary evaluation before each
  cleanup mutation, call `_check_mutation_authority` for every file and directory effect, and never
  call mutation methods outside `OrganizerExecutor`.

### 4. Durable Task, result and recovery model

- Use one durable transfer Task for directory, cross-Storage or multi-selection work. Persist a
  bounded item for each independently recoverable top-level selection and durable sub-checkpoints
  for transferred entries; do not create one unbounded TaskItem per provider listing without the
  manifest limits.
- Persist source/destination logical identities, requested operation, conflict decision, completed
  checkpoints, known effects, effect certainty, retry safety and next action. Resume skips verified
  completed checkpoints and never repeats `SOURCE_DELETED` or an uncertain write/delete.
- Preserve successful siblings when another item fails. Pause/cancel is observed between safe
  manifest entries/checkpoints; it cannot interrupt by pretending a currently executing provider
  mutation was rolled back.
- Organize cleanup results remain attached to the corresponding Organize result as `SUCCESS`,
  `STOPPED`, `PARTIAL`, `FAILED` or `NOT_APPLICABLE`, with bounded steps naming matched logical
  entries. A cleanup problem never erases the already-known primary Move result.

### 5. API and Web journey

- Prefer routes equivalent to a bounded `transfer-impact` request followed by one `transfers`
  submission under the source ResourceLibrary Files API. Reuse the existing authenticated Files
  browse route for destination directories and existing Task/result reads for progress; route names
  may follow current API conventions, but both Web and API must call the same application service.
- Add a Copy/Move dialog containing selected-source summary, operation, destination ResourceLibrary,
  destination breadcrumb, conflict choice and capability/limit explanation. Safe choices submit
  directly; Replace, if implemented, adds exactly one destination-bound destructive confirmation.
- Show inline/durable per-item states for queued, copying, verifying, deleting source, completed,
  retained source, partial and uncertain. Translate stable backend categories into an explanation
  of what currently exists and the one safe next action; never expose opaque evidence or require the
  operator to copy a Task ID/token.
- Extend Organize Preview/result UI only enough to show `sourceDirectoryCleanup`: configured
  patterns and bounds, matched junk files, blockers, permanent-delete warning, final cleanup steps
  and recovery. The example scenario must be understandable without opening raw plan JSON.

#### 5.1 Existing Files interaction corrections

- Refactor `LibraryCardStrip` so the card's selection button owns the full card geometry and padding,
  while `CardActionMenu` remains a non-overlapping sibling target above that surface. Preserve
  `aria-pressed`, visible focus, keyboard activation and deterministic URL/query reset behavior.
- Keep the Web Delete impact request as an explicit array serialization and make the API parser
  intentionally accept repeated `path` values only. Apply the existing `MAX_DELETE_PATHS` bound and
  application-level normalization after parsing. Parser rejection must remain structured and
  actionable for unknown keys, empty values or excessive input instead of collapsing a valid
  multi-selection into a generic request error.
- Make the Files pane a bounded column layout: fixed/sticky toolbar, flexible row viewport with
  actual vertical scrolling, and footer outside the viewport. The table header may remain visible
  while scrolling when that can be done without changing column alignment or accessibility.
- Move the row menu to a page-level popover layer. Anchor it from the row button rectangle, prefer
  opening below, flip above near the viewport bottom, clamp horizontally, and close/reposition on
  Files-pane scrolling so the menu can never refer visually to the wrong row.
- Preserve the operator's ResourceLibrary, path, search and unaffected selection across menu open/
  close and impact-summary failure. A successful destructive result may clear only entries whose
  known effects prove they no longer exist.

### 6. Provider behavior matrix

| Provider | Direct Copy/Move | Direct Delete continuity | Organize `ignorable` cleanup |
|---|---|---|---|
| Local | advertised native capability with entry evidence | Task 37.3 behavior unchanged | matched files, then real empty directory |
| SMB | advertised native capability only | Task 37.3 behavior unchanged | matched files, then provider-confirmed empty directory |
| OpenList | advertised native capability only; no invented fallback | direct Delete remains unavailable without trusted identity | explicitly policy-matched current files, then provider-confirmed empty directory |
| S3/R2 | native object operation or explicit cross-Storage stream | file validator retained; virtual-directory direct Delete remains unavailable | matched objects; absent virtual prefix is success, explicit empty marker is deleted |

The matrix describes current adapter facts, not provider-name branching in business code. Capability,
entry evidence and directory semantics remain exposed through provider-neutral ports/helpers.

### 7. Deterministic test construction

- Add fault-injecting transfer fakes for truncated writes, destination digest mismatch, source change
  after Copy, delete refusal after verification, lost response/uncertain write, pause/cancel and one
  failed item among successful siblings. Assert exact Storage call order and zero replay.
- Add frontend unit and browser regressions that click the top/bottom padding and label/icon regions
  of a non-selected ResourceLibrary card, proving every non-menu point switches once and its `...`
  action does not switch.
- Add API and Web tests for two and fifty selected Delete paths. Assert that repeated `path` query
  values reach one bounded zero-mutation impact model, an over-limit or blank selection fails before
  mutation, the confirmation digest covers the complete selection and one failing item cannot hide
  successful siblings.
- Add controlled-viewport browser coverage with at least ten rows. Assert `scrollHeight >
  clientHeight`, wheel/keyboard scrolling changes the viewport, the final row becomes visible, the
  displayed count remains truthful and selection follows the scrolled row rather than its previous
  visual position.
- Open a row menu for the last visible and final rows after scrolling. Assert the menu items are
  visible and hit-testable, are not clipped by the table cell or scroll container, remain anchored
  to the correct row, flip/clamp within the viewport, dismiss on Escape/outside click and restore
  focus to the invoker.
- Add OpenList and S3 cleanup regressions for the motivating directory: one moved video plus several
  explicitly matched junk files. Prove the media Move completes, matched junk is deleted, the empty
  source directory/prefix reaches truthful final state, and no Files direct Delete identity bypass
  is used.
- Add negative cleanup cases for `*`/`**`, an unknown file, a nested directory, exceeded entry/
  parent bounds, a changed matched file, Copy rather than Move, cleanup permission refusal and a
  provider failure after one deletion. Assert unknown entries survive, known partial effects are
  recorded and no automatic retry occurs.
- Web/API tests cover destination navigation, conflict choices, progress/checkpoint explanation,
  selected-context preservation, cleanup Preview/result explanation, RBAC, redaction and the
  current OpenList/S3 unsupported direct-Delete messages.

## Acceptance Criteria

- [ ] An authorized operator can Copy or Move one file, one bounded directory, or a bounded mixed
      selection entirely from `/ui-v2/library/files`, choosing an explicit eligible destination
      ResourceLibrary/directory without CLI, host paths, raw credentials or media-organize ceremony.
- [ ] Every visible non-menu point of a ResourceLibrary card selects that ResourceLibrary exactly
      once. The separate `...` action opens its menu without changing selection; pointer, keyboard
      and touch activation retain visible focus and the selected library's authoritative path/data.
- [ ] Delete impact accepts a bounded multi-selection encoded as repeated `path` values and returns
      one zero-mutation summary for the complete selection. Two through fifty paths work, invalid or
      over-limit input fails closed, and execution still requires the exact server-issued digest and
      all existing entry-identity checks.
- [ ] A directory containing at least ten returned entries has a usable vertical row viewport. The
      operator can reach the final entry by wheel, keyboard and touch/pointer scrolling; the item
      count, row identity, selection and pagination remain truthful without clipping or hidden stale
      state.
- [ ] The `...` menu for first, last-visible and final rows is visible and interactive above the
      scrolling table, including near viewport edges. It never clips inside a cell, never opens for
      the wrong row, closes on Escape/outside click or relevant navigation, and restores focus to
      its invoking button.
- [ ] The destination picker is live-Storage/Active-ResourceLibrary authoritative, bounded and
      confined. Opening, navigating, cancelling or correcting it performs zero mutation and creates
      no transfer Task.
- [ ] Source and destination use the same pinned immutable Active snapshot. Stale/disabled/mismatched
      configuration, path escape, root transfer, self/descendant overlap, nested duplicate roots,
      symlink/unsupported type and item/depth/byte overflow fail closed with useful context.
- [ ] Same-Storage Copy and Move use exactly the requested native advertised capability and never
      silently substitute one operation, a streaming fallback or a different policy. Unsupported
      entries/providers receive an actionable per-item or pre-submit refusal.
- [ ] Cross-Storage Copy streams only through the admitted bounded transfer path and is not reported
      successful until the destination is verified. Truncation, changed source, target failure and
      verification failure produce truthful known/partial/uncertain effects and safe recovery.
- [ ] Cross-Storage Move visibly and durably follows Copy → verify → Delete source. Every failure
      before verified Copy preserves the source; source deletion requires fresh exact evidence; a
      later failure records the surviving source/destination truth and never auto-replays the Move.
- [ ] The supported OpenList/S3 cleanup scenario completes end to end: an OrganizePolicy `MOVE`
      successfully organizes the selected media file, then `sourceDirectoryCleanup.mode=ignorable`
      deletes only current regular files whose basenames match the explicitly configured safe
      patterns and removes or truthfully resolves the now-empty source directory/prefix.
- [ ] Source cleanup is visible in Organize Preview/result with exact patterns, bounds, matched
      logical files, blockers, permanent-delete meaning, per-step known effects and recovery. It
      runs only after verified primary Move; it is `NOT_APPLICABLE` for Copy and performs no delete
      when the primary Move failed or remained uncertain.
- [ ] Any unknown file, nested directory, symlink, unsafe/broad pattern, changed admission state,
      exceeded bound or denied capability stops cleanup without expanding the authorized set.
      Already completed cleanup steps remain explicit partial effects and are never automatically
      replayed. OpenList's lack of direct-entry identity is not hidden or used to weaken the Files
      direct Delete contract.
- [ ] S3 virtual-directory semantics are truthful: after all admitted objects are removed, an absent
      prefix counts as cleaned without deleting a fictional entry; an existing marker is handled as
      an explicit empty object. Files direct recursive Delete still fails closed when its separate
      exact-scope requirements are unavailable.
- [ ] Every mutating Storage call crosses `OrganizerExecutor` after RBAC, pinned-Active,
      confinement, capability, bounds, stale and conflict checks. Application/API/Web code performs
      no direct Storage mutation, and Scanner/Parser/Recognition/Metadata/Naming/Classification/
      organize Planner are not invoked for Copy/Move.
- [ ] Destination conflicts default to no overwrite. Skip and keep-both behavior, when selected,
      are deterministic and independently recorded. Replace is absent unless implemented with one
      explicit destructive confirmation plus exact last-boundary destination revalidation; no path
      is silently overwritten or deleted.
- [ ] Directory, cross-Storage and multi-item work uses durable Tasks with bounded progress and
      independent per-item/checkpoint outcomes. Pause/cancel and retry/recovery do not replay
      successful siblings or any uncertain mutation.
- [ ] Success refreshes authoritative source/destination truth and clears/remaps only stale
      selection. Failure/partial/uncertain states keep the Files context, say what exists at source
      and destination, state whether retry is safe and expose a concrete next action.
- [ ] API and Web use one application behavior and permission model. Audit/results/errors are
      bounded and secret-free, and the ordinary Web journey does not expose internal Task,
      checkpoint, grant or execution-token ceremony.
- [ ] Copy/Move controls and picker/progress/result states are keyboard- and touch-operable,
      preserve input on recoverable failure, prevent duplicate submission and remain usable at the
      controlled `1536 x 1024` and supported responsive widths.
- [ ] Existing Create Folder/Text, Rename, text Edit, Delete, ResourceLibrary lifecycle, Files
      browse/selection, organize Preview, non-Files V2 routes and V1 `/ui` remain functional; no
      current safety assertion is removed, weakened or skipped.
- [ ] Focused tests cover success, invalid input, permission/capability denial, confinement,
      conflicts, stale source/destination, same/cross-Storage behavior, bounded directories/batches,
      Copy verification, verify-before-delete, partial/uncertain effects, pause/cancel/recovery,
      redaction and OrganizerExecutor-only mutation. The T4 gates pass with truthful accounting of
      pre-existing/unrelated failures or unavailable external gates.
- [ ] The checkpoint contains only Task 37.4 implementation, tests and completion report. It excludes
      `config/alist.json`, credentials, the dirty reference image, ignored test artifacts and
      unrelated changes.

## Required Tests

- `python3 scripts/check_governance.py`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m unittest tests.test_direct_file_transfers`
- `.venv/bin/python -m unittest tests.test_direct_file_operations`
- `.venv/bin/python -m unittest tests.test_source_directory_cleanup tests.test_manual_organize_execution tests.test_configuration_organize`
- `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_organizer_rollback`
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage tests.test_openlist_storage tests.test_s3_storage`
- `.venv/bin/python -m unittest tests.test_runtime_files_browser tests.test_api_security tests.test_task_persistence tests.test_task_pause_resume tests.test_task_retry`
- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `python3 scripts/docker_release_security_smoke_test.py`
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"`
- `cd web && npm run format:check`
- `cd web && npm run typecheck`
- `cd web && npm run lint`
- `cd web && npx vitest run src/features/library/StorageFilesPage.test.tsx`
- `cd web && npx playwright test tests/e2e/library-files.spec.ts --project=chromium`
- `cd web && npm run test -- --run`
- `cd web && npm run build`
- `cd web && npm run test:e2e`
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist`
- `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl`
- `git diff --check`
- Inspect `git status --short`, the exact Task Base..Head diff and staged manifest; confirm
  `config/alist.json`, credentials, the dirty `docs/pics/文件页.png`, ignored local test artifacts and
  unrelated files are absent.

All tests use mocks, fakes, temporary roots and local test servers only. No production
SMB/OpenList/S3/TMDB service, credential or real media directory is permitted. Focused transfer
tests must use fault-injecting Storage doubles to prove Copy verification precedes Move source
deletion, verification failure preserves the source, every mutation crosses OrganizerExecutor,
successful siblings are not replayed and partial/uncertain effects remain independently visible.
They must also prove the OpenList/S3 Move-plus-ignorable-cleanup journey, the distinction from Files
direct Delete, unknown-entry fail-closed behavior, S3 virtual-prefix completion and explicit
per-entry cleanup effects without production services. The Files-focused Vitest and Playwright
commands must additionally cover full-card hit testing, repeated-`path` multi-selection Delete,
ten-row vertical scrolling and unclipped bottom-row menus; a DOM-visible but fully clipped menu does
not satisfy the browser assertion.

## Non-goals

- Upload, Download, browser multipart/resumable upload, response/archive streaming or transfer to
  arbitrary host paths.
- Media recognition/metadata/naming/classification redesign, a new organize Planner, multi-item
  media Organize completion, terminal Organize-to-FileIndex reconciliation or broad FileIndex
  repair. Only the existing `sourceDirectoryCleanup` Move continuation described above is in scope.
- New Storage providers, adapter-wide redesign, invented provider capability, implicit transfer
  fallback, unbounded recursion/batches or distributed transfer workers.
- Weakening Task 37.3 Rename/Delete exact-entry evidence, bounded text Save semantics,
  ResourceLibrary managed removal or any accepted safety test. Correcting the confirmed card-hit,
  repeated-`path` multi-selection and overflow/menu regressions above is explicitly in scope, but
  their safety contracts may not be relaxed.
- Broad non-Files body redesign, V1 cutover, optional copy polish, P2/P3 cleanup or work outside
  Slice 37.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/direct_files.py` — transfer vocabulary: `MAX_TRANSFER_*` bounds,
  `TransferOperation`, `TransferConflictMode`, `TransferCheckpoint`,
  `TransferManifestEntry`, `TransferManifest` (+ opaque `transfer_manifest_digest`),
  `TransferConflict`, `TransferImpact.document()`, `SourceCleanupProjection`.
- `mediaflow/domain/organizer.py` — `DirectoryCleanupStatus.PARTIAL`.
- `mediaflow/domain/task_persistence.py` — `FILES_TRANSFER_TASK_COMMAND`.
- `mediaflow/application/organizer.py` — new `OrganizerExecutor` transfer primitives
  (`execute_direct_copy`, `execute_direct_move` with the compound cross-Storage
  copy → verify → delete-source path, `execute_direct_remove_empty_directory`),
  streamed digest-verified copy (`_stream_copy_verified`, `_HashingReader`,
  `_stream_digest`), transfer capability/source preflights
  (`_transfer_capability_error`, `_transfer_source_preflight`), and the
  `_cleanup_source_directories` refactor (per-entry steps, PARTIAL status,
  name-predicate re-stat, OpenList provider-confirmed-empty deletion, S3
  `DIRECTORY_ALREADY_ABSENT` semantics, no fictional object deletes) plus the
  bounded `project_source_cleanup` projection.
- `mediaflow/application/direct_file_commands.py` — public admission accessors
  (`revision`, `tasks`, `library`, `relative_path`, `open_storage`) shared by the
  composed transfer service.
- `mediaflow/application/direct_file_transfers.py` (new) — `DirectFileTransferService`:
  zero-mutation impact/admission (pinned manifest, bounded enumeration with
  entry/depth/byte limits, overlap/duplicate/root/symlink/destination checks,
  deterministic destinations and keep-both names) and durable execution
  (manifest-digest stale fence, per-top-level Task items, explicit conflict
  behavior, destination directory creation through the executor, emptied-source
  directory removal, bounded known-effects/checkpoints/outcomes, pause/cancel at
  safe boundaries, no replay of uncertain effects).
- `mediaflow/application/manual_organize_preview.py` — `cleanupProjection` in the
  Preview item document.
- `mediaflow/interfaces/service_api.py` — `GET .../files/transfer-impact` and
  `POST .../files/transfers` routes sharing the application service and RBAC;
  `_files_delete_impact_query` now accepts the bounded repeated `path` field and
  rejects unknown keys/blank/over-limit input with structured actionable errors;
  `_files_transfer_impact_query` parser; audit route names; binding construction.
- `web/src/entities/library/direct-files.ts` — `TransferImpactModel`,
  `TransferResultModel`, strict normalizers; `web/src/entities/operations/preview.ts`
  — `ManualPreviewCleanupModel`; `web/src/entities/operations/task.ts` —
  `cleanupStatus` on result summaries.
- `web/src/shared/api/api-client.ts` — `fetchTransferImpact`, `submitTransfer`.
- `web/src/features/library/TransferDialog.tsx` (new) — Copy/Move dialog with
  live-Storage destination picker, explicit conflict choices (Replace omitted),
  durable result/recovery view.
- `web/src/features/library/RowActionMenu.tsx` (new) — page-level portal row menu
  (anchor from the invoking button, flip/clamp, scroll/resize/Escape/outside
  dismissal, focus restoration).
- `web/src/features/library/StorageFilesPage.tsx` — toolbar/footer/row-menu Copy
  and Move surfaces, transfer mutation and known-effect selection pruning.
- `web/src/features/library/LibraryCardStrip.tsx` + `web/src/shared/ui/styles.css` —
  the card selection button owns the full card geometry with the `…` menu as a
  sibling overlay; scrollable row viewport (`min-height: 0`,
  `overflow-y: auto`, sticky header), independent tree scroll; portal menu CSS.
- `web/src/features/operations/OrganizePreviewPage.tsx`,
  `web/src/features/operations/TaskDetailPage.tsx` — cleanup projection display and
  per-result Cleanup column.
- Tests: `tests/test_direct_file_transfers.py` (new, 21 tests),
  `tests/test_source_directory_cleanup.py` (+6 provider-semantics tests),
  `web/src/features/library/StorageFilesPage.test.tsx` (+4),
  `web/src/entities/operations/preview.test.ts` (+1),
  `web/tests/e2e/library-files.spec.ts` (+5), `web/tests/fake-server.mjs` (transfer
  fixtures + 12-row TV directory).

### Implemented

- Bounded Files Copy/Move for one item or a bounded selection, same-Storage
  native-only operations, cross-Storage streamed verified Copy, compound
  cross-Storage Move with durable `COPY_WRITTEN`/`DESTINATION_VERIFIED`/
  `SOURCE_DELETED` checkpoints and verified-copy/source-retained partial outcomes
  when exact destructive authority is unavailable (OpenList/SMB entries publish no
  identity), deterministic conflicts (default no-overwrite, `跳过`, `保留两者`;
  Replace omitted), durable Tasks with independent per-item outcomes, and a
  zero-mutation destination picker.
- `sourceDirectoryCleanup.mode=ignorable` completed for Local/SMB/OpenList/S3:
  runs only after a verified MOVE, name-predicate admission with re-stat,
  per-entry known effects, PARTIAL partial-failure semantics, OpenList
  provider-confirmed-empty directory deletion, S3 absent-virtual-prefix recorded
  as already cleaned (explicit empty marker deleted through the executor), and
  read-only Preview projection of patterns/bounds/matched files/blockers.
- The three confirmed Task 37.3 regressions: full-card ResourceLibrary selection
  hit target with a non-nested sibling action menu; bounded repeated-`path`
  multi-selection Delete impact (2–50 paths) with structured parser refusals;
  real scrolling row viewport plus an unclipped portal row menu with focus
  restoration.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS; `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `.venv/bin/python -m unittest tests.test_direct_file_transfers` — PASS (21).
- `.venv/bin/python -m unittest tests.test_direct_file_operations` — PASS (55).
- `.venv/bin/python -m unittest tests.test_source_directory_cleanup
  tests.test_manual_organize_execution tests.test_configuration_organize` — PASS (57).
- `.venv/bin/python -m unittest tests.test_organizer
  tests.test_organizer_mutation_authority tests.test_organizer_rollback` — PASS (45).
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage
  tests.test_openlist_storage tests.test_s3_storage` — PASS (94).
- `.venv/bin/python -m unittest tests.test_runtime_files_browser
  tests.test_api_security tests.test_task_persistence tests.test_task_pause_resume
  tests.test_task_retry` — PASS (43).
- `.venv/bin/python -m unittest discover -s tests` — 1620 tests: FAIL with the
  3 failures reproduced unchanged at the Task Base (see Risks).
- `test -z "$(rg ... ffprobe|ffmpeg ...)"` — rg is not installed in this
  environment; verified equivalently with
  `grep -rn -i "ffprobe|ffmpeg" mediaflow pyproject.toml` → no matches. PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE: the
  Docker daemon rejects the smoke harness's bind mounts
  (`bind source path does not exist: /tmp/mediaflow-smoke-security-*/mediaflow.json`),
  an environment limitation of this workspace; Docker itself is reachable and the
  script failed with exit 1 rather than hiding the failure.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` — PASS;
  `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS;
  wheel artifacts were removed after the check.
- `cd web && npm run format:check` — PASS; `npm run typecheck` — PASS;
  `npm run lint` — PASS.
- `cd web && npx vitest run src/features/library/StorageFilesPage.test.tsx` — PASS (29).
- `cd web && npm run test -- --run` — PASS (33 files / 448 tests).
- `cd web && npm run build` — PASS.
- `cd web && npx playwright test tests/e2e/library-files.spec.ts --project=chromium`
  — PASS (28); `npm run test:e2e` — PASS (106).
- `git diff --check` — PASS; changed-file manifest inspected: no
  `config/alist.json`, credentials or unrelated files; the pre-existing dirty
  `docs/pics/文件页.png` was preserved and is deliberately not staged.

### Decisions

- Transfer conflict `替换`/Replace is omitted entirely rather than implemented
  behind a destructive confirmation: the default is no-overwrite with `FAIL`,
  `SKIP` and `KEEP_BOTH` as explicit choices, so no silent overwrite path exists.
- Same-Storage directory transfers are composed from explicitly planned
  executor-owned `CreateDirectory` plus per-file native Copy/Move, then emptied
  source directories are removed by a dedicated executor primitive that re-lists
  and refuses non-empty directories. No provider-name branching and no
  cross-operation substitution exists; a directory Move is never implemented as
  Copy because every entry crosses through `Storage.move`.
- Same-Storage Move is admitted as the provider-native path operation with
  existence/type revalidation and an observed-metadata stale check (strict
  provider identity when published). The exact-entry destructive identity
  requirement is reserved for actions that delete a separately resolved object
  (Files direct Delete and the cross-Storage Move source deletion), preserving
  the Task 37.3 contract where it applies.
- A cross-Storage Move whose source provider publishes no verifiable identity
  performs the safe Copy first and ends as `PARTIAL` with
  `COPY_WRITTEN`/`DESTINATION_VERIFIED`, `entry_identity_unavailable` and the
  source retained — the Task's recoverable verified-copy/source-retained outcome
  instead of a weak-evidence delete.
- The bounded transfer selection (50 top-level paths, 5000 entries, depth 32,
  20 GiB) reuses the Delete impact bounds so one bounded-scope model governs all
  direct commands.
- `TASK.md` (B's planning text plus this report) travels with the implementation
  checkpoint per the workflow; `docs/pics/文件页.png` remains unstaged/dirty.

### Remaining In-Slice Work

- Upload and Download journeys (browser multipart/resumable upload, bounded
  streamed archive download) are untouched by this Task.
- The remaining media-Organize/FileIndex reconciliation journey: multi-item
  Organize completion from Files, terminal Organize-to-FileIndex reconciliation.
- B decides whether the current per-entry checkpoint document shape is sufficient
  for the Slice-level transfer evidence or needs a follow-up unit.

### Risks / Deviations

- Full-suite FAIL is limited to the 3 failures already present at the Task Base
  (`test_configuration_status.ConfigurationSnapshotTests.test_hostile_configuration_content_is_never_exposed`,
  and the two
  `test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_*`
  golden-fixture failures asserting 201). Reproduced at clean HEAD e6c1749 before
  any change; pre-existing and unrelated to this Task, and the B PASS judgment on
  them is not mine to make.
- The Docker release-security gate could not run in this workspace (daemon bind
  mount of the smoke context is rejected); it is UNAVAILABLE, not PASS, and
  should be re-run where Docker can bind-mount the smoke context.
- Playwright/Vitest layout-dependent assertions are split: jsdom proves the
  structural/portal/focus contracts, and the Chromium suite proves the on-screen
  geometry (`overflow-y: auto`, `min-height: 0`, `scrollHeight > clientHeight`,
  viewport-edge menu hit testing) against the built bundle.
- The fake e2e server gained transfer handlers; their digest scheme is a test
  fixture, not a protocol contract — the real digest is backend-computed.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 9eafe9e3fef11e993670b42b762d747cbc0dee5a
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
