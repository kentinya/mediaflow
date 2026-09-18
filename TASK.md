# Task 37.4 — Files Bounded Copy and Move Transfers

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.4
Parent Slice: 37
Status: FIX REQUIRED
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

> Correction round 8, 2026-09-18: this report covers the two blockers of the B
> review of `4954502..0426708` (transfer-item admission wrote the `PROCESSING`
> TaskItem before ownership was proven, and the production takeover regression
> weakened the exact terminal assertion to a set-membership check). It
> supersedes the round-7 report. The correction commit sits after the round-7
> checkpoint `0426708` without amending it.

### Changed Files

- `mediaflow/application/task_runtime.py` — `begin_item` is now one
  claim-fenced ownership boundary. The started row is published only through
  `upsert_item_guarded` (compare-and-set against the live claim) instead of an
  unguarded `upsert_item`; a failed acquisition against a lapsed claim raises
  `TaskClaimLost` with zero writes; a failed acquisition against a *live* claim
  still publishes the bounded lock failure, now under the same fence; a valid
  continuation reuses the predecessor's row via `replace(previous, ...)` so the
  durable recovery checkpoint survives the start boundary; a failed guarded
  start publish releases only this frame's exact generation and performs no
  compensating TaskItem write. Two small private helpers were added:
  `_claim_is_current` (fails closed when the repository cannot answer) and
  `_publish_item_start` (guarded when fenced, historical unguarded write
  otherwise). The unfenced Organize/manual-execution path is byte-for-byte
  unchanged.
- `tests/test_direct_file_transfers.py` — the production takeover regression
  restores the exact `status == "completed"` assertion and adds
  `_assert_completed_transfer_agreement`, which proves the transfer row, Task
  row, every TaskItem, every Result, the Files projection and the Operations
  detail agree and then re-reads them from a freshly reopened repository on the
  same database file. Three new regressions were added:
  `test_stale_claimant_continuation_changes_no_durable_evidence`,
  `test_continuation_crash_window_keeps_the_prior_checkpoint` and
  `test_lost_ownership_at_every_handoff_boundary_writes_nothing`, plus an
  `_admit_show_transfer` fixture helper.

### Implemented

- **The blocker — no TaskItem write before ownership is proven.** I first
  reproduced B's repro exactly against the round-7 code: a stale Worker A raised
  `TaskClaimLost` and left B's lock owned, but had already rewritten B's row from
  `progress={"owner":"worker-b"}, attempts=1` to `progress=None, attempts=2`.
  The unguarded `self.repository.upsert_item(item)` that ran before
  `adopt_or_acquire` is gone. The start row now goes through
  `upsert_item_guarded`, so the claim CAS and the write are one atomic
  transaction: a lost claimant writes nothing.
- **Every transfer-path TaskItem write is fenced.** The `PROCESSING`/attempt
  start update and the lock-conflict `FAILED` update both publish under the
  fence. There is no longer any unguarded write after a successful claim check,
  so a claim lost between any two calls cannot surface as a stale publication.
- **No attempt consumed and no fabricated failure for a stale acquisition.** A
  failed acquisition against a lapsed claim raises `TaskClaimLost` before any
  write, so `attempts`, `status`, `stage`, `updated_at`, `progress` and `error`
  are all untouched and no Result is written. A failed acquisition against a
  genuinely live foreign claim still publishes the bounded lock failure — that
  is a real refusal, not a stale one.
- **The durable checkpoint survives a valid continuation.** For a fenced
  continuation the row is built with `replace(previous, ...)` rather than a
  fresh `progress=None` item, so the predecessor's recovery checkpoint is the
  authority a crash between the start boundary and the first new progress write
  leaves behind. The checkpoint is superseded only by a later claim-guarded
  progress or terminal publication. A crash there no longer degrades to
  `files_transfer_interrupted_unknown`.
- **Round-7 lock properties preserved.** Same-Task handoff is still an in-place
  rotation (`adopt_or_acquire` / `rotate_task_locks` untouched); a different
  Task's row still fails closed; a predecessor's late release is still an exact
  no-op; the production takeover path still does not call blanket
  `reclaim_task_locks`; and no new persistent lifecycle state was introduced.
  When the guarded start publish fails, only this frame's exact generation is
  released, so a replacement owner's row is never touched.
- **The weakened assertion is restored, not replaced.** The production takeover
  regression asserts `runtime.get_task(task_id).status.value == "completed"`
  exactly — no set membership, no conditional, no skip — and additionally
  asserts the transfer row is `completed`, the Files projection is `SUCCESS`
  with `succeededItems == 1` and zero failed/skipped, every TaskItem is
  `success`/`completed` with no error and no in-flight marker, the single Result
  is `success`/`verified_complete` with no uncertain effects, and the Operations
  detail agrees. The same rows are then re-read from a repository reopened on
  the same database file.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (307 files already formatted);
  `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m unittest tests.test_direct_file_transfers` — PASS (82,
  was 79 in round 7: three new regressions).
- `.venv/bin/python -m unittest tests.test_direct_file_operations
  tests.test_task_persistence` — PASS (68; 55 + 13).
- `.venv/bin/python -m unittest tests.test_direct_file_transfers
  tests.test_direct_file_operations tests.test_task_persistence` — PASS (150).
- `.venv/bin/python -m unittest tests.test_direct_file_transfers
  tests.test_direct_file_operations tests.test_task_persistence
  tests.test_task_pause_resume tests.test_task_retry` — PASS (166).
- `.venv/bin/python -m unittest tests.test_source_directory_cleanup
  tests.test_manual_organize_execution tests.test_configuration_organize
  tests.test_organizer tests.test_organizer_mutation_authority
  tests.test_organizer_rollback tests.test_local_storage tests.test_smb_storage
  tests.test_openlist_storage tests.test_s3_storage tests.test_runtime_files_browser
  tests.test_api_security tests.test_task_pause_resume tests.test_task_retry` —
  PASS (231).
- `.venv/bin/python -m unittest discover -s tests` — 1686 tests: 3 failures,
  7 skips. The 3 failures are exactly the Task Base baseline and were reproduced
  identically at a clean `4954502` worktree during this round:
  `test_configuration_status.ConfigurationSnapshotTests.
  test_hostile_configuration_content_is_never_exposed` and the two
  `test_manual_operations_contract.ManualOperationsContractTests.
  test_real_api_documents_*` golden-fixture failures asserting 201. Pre-existing
  and unrelated; whether they block PASS is B's judgment, not mine.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS;
  `.venv/bin/python -m pip check` — PASS (no broken requirements).
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE in this
  workspace, unchanged from the previous rounds: `docker compose up -d
  --no-build` fails with `invalid mount config for type "bind": bind source path
  does not exist: /tmp/mediaflow-smoke-security-*/mediaflow.json`, i.e. the smoke
  context cannot be bind-mounted here. Not a product failure. `rg` is also absent
  in this workspace, so the ffprobe/ffmpeg gate was run with
  `grep -rniE 'ffprobe|ffmpeg' mediaflow pyproject.toml` — PASS (no match).
- `cd web && npm run format:check` — PASS; `npm run typecheck` — PASS;
  `npm run lint` — PASS (0 errors); `npm run build` — PASS.
- `cd web && NODE_ENV=test npm run test -- --run` — PASS (33 files / 455 tests).
- `cd web && NODE_ENV=test npx playwright test
  tests/e2e/library-files.spec.ts --project=chromium` — PASS (28).
- `cd web && NODE_ENV=test npm run test:e2e` — 106 passed, 10 failed; the same
  10 failures (`library-file-detail` 7 + `manual-operations` 3) that reproduce
  identically at a clean `4954502` worktree. This correction changes no web file.
  Pre-existing and unrelated; B judges.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` — PASS;
  `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS
  (schema 38, database verify OK).
- `git diff --check` — PASS (no whitespace errors).

New regression evidence for this correction, run explicitly:

- `test_stale_claimant_continuation_changes_no_durable_evidence` — after Worker B
  owns the claim, the exact lock generation and a distinctive durable checkpoint,
  stale Worker A's continuation raises `TaskClaimLost` with `attempts` still 1,
  `progress` unchanged, `error` unchanged, no Result, zero Storage mutation, B's
  replacement lock generation still owned, the transfer mutation boundary and
  claim token unchanged, and the lock-row snapshot identical. Verified
  falsifiable: reintroducing the round-7 unguarded pre-acquisition write makes it
  fail with `attempts: 2, progress: None`, i.e. B's exact observation.
- `test_continuation_crash_window_keeps_the_prior_checkpoint` — B crosses the
  guarded start boundary (attempts 1→2) and stops before any new progress; after
  a repository reload the item is still `processing` with the original
  checkpoint, and `_resume_item_plan` reconstructs the original admitted plan
  (`show → Movies/show`, `show/ep00.mkv → Movies/show/ep00.mkv`) instead of
  degrading to investigation-only. Verified falsifiable: the round-7 fresh-row
  shape makes `progress` become `None`.
- `test_lost_ownership_at_every_handoff_boundary_writes_nothing` — covers lost
  ownership before the Task-wide rotation (rotation returns 0 rows), between the
  rotation and the per-item adoption, and after the start boundary: each case
  raises `TaskClaimLost` and leaves `status`/`stage`/`attempts`/`progress`/`error`,
  Results, the mutation boundary and the lock generation exactly as they were.
- Round-7 regressions retained and passing:
  `test_production_shaped_continuation_denies_a_competing_task` (now with the
  exact `completed` assertion and cross-surface reload agreement),
  `test_takeover_handoff_never_leaves_the_source_path_unowned`,
  `test_failed_cas_never_removes_the_replacement_generation`,
  `test_post_publication_expiry_window_keeps_the_replacement_generation`,
  `test_live_mutation_keeps_its_exclusion_and_the_owner_retires_it`,
  `test_lock_generations_never_reach_operator_documents`.

No existing assertion was weakened, hidden, relaxed or skipped, and the Task
Base was not changed.

### Decisions

- **Reuse `upsert_item_guarded` for the start publication rather than adding a
  parallel guarded API.** It already implements exactly the required
  compare-and-set and the caller is inside one transaction. Its atomic
  `_clear_mutation_locked` side effect is a no-op here because the transfer path
  resolves any recorded `mutation_in_flight` boundary *before* executing items
  (see `run_claimed_transfer`), so no boundary can still be set at the start
  boundary. This avoids a new repository method for the same guarantee.
- **Distinguish a lapsed claim from a live foreign owner by re-reading the
  claim.** A failed acquisition is ambiguous, so `begin_item` checks
  `transfer_claim_is_current`: not current → `TaskClaimLost` with zero writes;
  current → the bounded lock failure, published under the fence. This preserves
  the existing `TaskLockError`/`stage="lock"` behaviour that
  `test_lock_conflict_is_persisted_without_storage_access` depends on while
  making a stale claimant silent.
- **Keep the predecessor's row for a fenced continuation.** Reusing the row is
  what makes the checkpoint survive the start boundary; minting a fresh row is
  what erased it. The unfenced path keeps the original fresh-row construction so
  Organize semantics are untouched.
- **Release only the exact generation when the guarded start publish fails, as
  B prescribed.** The delete names this frame's token, so a replacement owner's
  rotated row matches nothing and is untouched; the exclusion invariant still
  arbitrates because whichever Task holds the row denies every other Task.
- **Prove cross-surface agreement by reloading the database file.** Asserting
  against the same in-memory connection could pass while a projection disagreed,
  so the agreement check reopens `runtime._path` and re-reads every row.

### Remaining In-Slice Work

- Upload and Download journeys (browser multipart/resumable upload, bounded
  streamed archive download) are untouched by this Task.
- The remaining media-Organize/FileIndex reconciliation journey: multi-item
  Organize completion from Files, terminal Organize-to-FileIndex reconciliation.
- Whether the V2 Operations/Task-detail surface should render the transfer
  projection document is B's call; the Files dialog journey is complete without
  it.

### Risks / Deviations

- Full-suite FAIL is limited to the same 3 failures reproduced identically at a
  clean Task Base worktree (`4954502`):
  `test_configuration_status.ConfigurationSnapshotTests.
  test_hostile_configuration_content_is_never_exposed` and the two
  `test_manual_operations_contract.ManualOperationsContractTests.
  test_real_api_documents_*` golden-fixture failures asserting 201. Pre-existing
  and unrelated to this Task; whether they block PASS is B's judgment, not mine.
- Full e2e FAIL is limited to the 10 failures in `library-file-detail` (7) and
  `manual-operations` (3) that fail identically at the Base. This correction
  changes no web file. Pre-existing and unrelated; B judges.
- The Docker release-security gate remains UNAVAILABLE in this workspace; it needs
  a host where Docker can bind-mount the smoke context.
- The runtime schema is unchanged at 38; this correction changes one application
  method and its tests only and adds no migration.
- The architecture document still says "runtime schema `34`" — already stale
  before this Task (the committed Base declared 37) and left alone rather than
  widening this correction into a docs reconciliation.
- A lock row for a Task whose claim owner is lost and whose frame never returns
  (a hard process kill) is still retired only by the next authoritative
  takeover, cancel or pause — exactly as at the Base.
- A proven same-Storage Move whose source disappeared is adopted only when the
  provider publishes a fingerprint that still matches the admitted entry.
  `LocalStorage` fingerprints include `ctime`, which a native rename legitimately
  bumps, so such a Move is normally reported as `UNCERTAIN`/investigation rather
  than silently adopted — the conservative direction the plan requires.
- The lease keeper is a bounded daemon thread per invocation that stops with the
  invocation; it adds no persistent background worker.
- Per-item durable progress still stores the confirmed entry scope bounded at
  `MAX_TRANSFER_PROGRESS_ENTRIES` (512): an item whose recorded progress is
  truncated cannot be continued after an interruption and stops with an
  actionable investigation state — the same bounded, documented
  recovery-authority limitation as the previous rounds.
- Vitest and Playwright must run with `NODE_ENV=test` in this shell (see Tests
  and Results).
- The transfer Task aggregate still stores the canonical aggregate directly; an
  all-skipped batch is a COMPLETED durable row whose Files projection reports
  `SKIPPED`, matching the projection vocabulary.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 0ff0e664e9a937d3aa5f9aae288d98de480a27fb
```

## B Re-review Findings — 2026-09-17

B independently re-reviewed the explicit Task range
`4954502c6493d57634a14461a7268120419319da..9eafe9e3fef11e993670b42b762d747cbc0dee5a`
against this Task, Slice 37 and the actual implementation. The earlier PASS is rejected. These are
current Task blockers and remain in the Task 37.4 correction loop; Task 37.5 is not active until
this Task passes.

### F-1 — P0: directory conflict intent is bypassed

The impact phase reports an existing top-level destination directory as
`fail_no_overwrite`, but execution skips conflict handling for directory entries when the target
directory exists and proceeds with their children. A reproduced `MOVE` with conflict mode `FAIL`
returned `SUCCESS`, merged the file into the existing target directory and removed the source:

```text
declared_conflict = [('show', 'fail_no_overwrite')]
result_status = SUCCESS
source_still_exists = False
destination_file_exists = True
```

Required correction:

- Apply the selected conflict mode to every top-level and nested directory/file destination before
  mutation. `FAIL` performs zero mutation for that affected item; `SKIP` records a truthful
  skipped item; `KEEP_BOTH` pins one unique root and all descendants beneath it.
- Revalidate the exact destination conflict state at the last safe boundary. A conflict that appears
  after admission must fail/skip truthfully and must never become an implicit merge.
- Detect collisions inside the submitted batch, including two selected roots that resolve to the
  same destination basename. One sibling must not create a conflict that is later misreported as an
  external or uncertain effect.
- A directory `MOVE` may remove no source entry when the selected conflict behavior says the item
  must fail or skip.

### F-2 — P1: same-Storage native-only execution is not preserved

The manifest determines same Storage from configured Storage identity, while
`OrganizerExecutor.execute_direct_copy/move` determines it from Python object identity. Normal
runtime adapter construction can return a new adapter object for each `open_storage` call.
The reproduced production-style path reported `sameStorage=True` but invoked both executor
cross-Storage branches:

```text
copy manifest_same_storage = True; cross_copy_branch_calls = 1
move manifest_same_storage = True; cross_move_branch_calls = 1
```

Required correction:

- Bind one adapter instance per configured Storage identity for the complete impact/execution
  boundary, or pass an explicit validated same-Storage decision into the executor. Do not use
  incidental object identity as the business decision.
- Prove that same-Storage Copy calls only the advertised native `Storage.copy` and same-Storage
  Move calls only `Storage.move`; no streaming Write/Delete fallback is allowed.
- Make overlap checks compare the fully resolved confined logical Storage paths, including different
  ResourceLibrary roots on the same Storage. ResourceLibrary-relative strings alone must neither
  falsely reject distinct paths nor miss a physical self/descendant overlap.

### F-3 — P1: skipped and partial effects are persisted as fabricated success

A reproduced conflict with `SKIP` produced an entry outcome of `SKIPPED`, but the aggregate
response, known effect and durable Result said that the item succeeded and was transferred:

```text
skip_response_status = SUCCESS
skip_outcome = SKIPPED
skip_known_effect = transferred
skip_persisted_status = success
```

Directory creation/removal checkpoints can likewise fail without changing the top-level item status,
because only file outcomes participate in the current aggregation.

Required correction:

- Persist `SKIPPED` as `TaskItemStatus.SKIPPED` with a retained/skipped known effect; never count
  it as transferred or successful mutation.
- Include destination-directory creation and source-directory removal in item effect aggregation.
  If any directory mutation completed before a later failure, report a partial known effect. If an
  emptied source directory cannot be removed, do not report the directory Move as wholly successful.
- Aggregate all-skipped, mixed success/skipped, partial and uncertain batches truthfully.
- Web state pruning must distinguish Copy from Move. A successful Copy leaves the source present and
  selected unless another truthful state change requires pruning.

### F-4 — P1: durable Result identity and checkpoints are incomplete or wrong

For a reproduced cross-Storage Copy from `source-storage` to `media-target`, the persisted Result
recorded both source and destination Storage as `source-storage`, and persisted no completed
operations:

```text
persisted_source_storage = source-storage
persisted_destination_storage = source-storage
expected_destination_storage = media-target
persisted_completed_operations = ()
```

The detailed per-entry outcomes and Copy/verify/delete checkpoints currently exist only in the
synchronous HTTP response.

Required correction:

- Persist the exact destination Storage and ResourceLibrary identity, logical source/target paths,
  operation, conflict choice, same/cross-Storage mode, per-entry status, known effects, checkpoints,
  effect certainty, retry safety and stable recovery category.
- Reloading Task/Result detail after the request or process ends must reproduce the truthful
  per-item state needed for diagnosis and recovery; it must not depend on the original response.
- Keep this evidence bounded and secret-free. Do not persist host roots, credentials, raw provider
  payloads/exceptions or content.

### F-5 — P1: long transfer Task lifecycle is only synchronous decoration

Execution runs the whole transfer inside the POST request. Pause/cancel is checked only between
top-level selections, so one selected directory can process thousands of entries without observing
either request. There is no persisted transfer manifest/checkpoint authority from which the
resident Task machinery can safely continue after process interruption.

Required correction:

- Directory, cross-Storage and multi-item work must execute as genuine durable Task work with
  persisted bounded authority and independently durable item/checkpoint progress.
- Observe pause/cancel at safe per-entry or compound-checkpoint boundaries inside one directory.
  Completed effects remain terminal; uncertain mutations are never replayed.
- Define and test process-interruption recovery. Work may continue only from a persisted known-safe
  checkpoint; otherwise it must stop with an actionable uncertain/investigation state.
- A short same-Storage single-file command may remain synchronous only when it uses the same
  persistence, audit and executor safety semantics.

### F-6 — P1: the Web journey does not expose promised progress and item recovery

The dialog waits for the synchronous request and then renders only top-level `knownEffects`.
Although the response contains entry outcomes/checkpoints, they are not displayed. The impact fetch
also has a duplicate-submit window before the mutation state becomes pending.

Required correction:

- Show bounded per-item progress/outcome, checkpoint/known-state explanation and the safe next action
  for failed, partial and uncertain entries without exposing internal execution-token ceremony.
- Prevent duplicate submission across both impact acquisition and execution.
- Preserve destination and conflict input after recoverable failure, refresh live source/destination
  truth after known effects, and prune/remap only entries whose physical source truth changed.
- Prove destination navigation and action availability remain usable with paginated directories,
  keyboard/touch input and supported responsive widths.

## Correction Acceptance and Required Regression Tests

All original Task 37.4 Acceptance Criteria and Required Tests remain in force. The correction must
also add focused automated coverage for:

- top-level and nested destination-directory conflicts under `FAIL`, `SKIP` and `KEEP_BOTH`,
  including a directory `MOVE` proving `FAIL` leaves the complete source untouched;
- same configured Storage opened through the normal runtime factory without injected shared adapter
  instances, proving native Copy/Move calls and zero streaming/Delete fallback;
- distinct ResourceLibrary roots on one Storage, covering valid transfers plus real self/descendant
  overlap;
- truthful all-skipped/mixed/partial directory aggregation, failed destination-directory creation
  and failed emptied-source-directory removal;
- cross-Storage durable Result reload with the correct destination identity and persisted
  Copy/verify/delete checkpoints;
- pause/cancel within one large selected directory and process-interruption behavior at every
  compound Move checkpoint;
- Web per-item outcome/recovery presentation, Copy selection preservation and duplicate-submit
  prevention during impact acquisition.

The Developer must rerun the original T4 gate list, report the exact totals and reproduce or
truthfully account for the three pre-existing full-suite failures and the unavailable Docker gate.
No existing safety assertion may be removed, weakened or skipped to obtain a pass.

## Prior B Review Result — 2026-09-17

```text
Reviewed: 4954502c6493d57634a14461a7268120419319da..98e4175ceefd87ec327562379306918ab6ef43f9
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Runtime schema 34 -> 35 migration is broken for every subsequent TaskItem insert. On an upgraded
  database, `ensure_task_occurrence_columns` has already appended the three source-occurrence
  columns, then schema 35 appends `progress` at the physical end; `_item_values` and every
  positional `INSERT INTO task_items VALUES (...)` instead place `progress` immediately after
  `error`. B's isolated schema-34 reproduction fails in `SQLiteTaskRepository.upsert_item` with
  `sqlite3.IntegrityError: NOT NULL constraint failed: task_items.source_fingerprint_state`.
  Replace positional inserts with explicit column lists (including all alternate/atomic insert
  paths), make fresh and upgraded layouts order-independent, and add a real 34 -> 35 migration
  regression that persists/reloads both an ordinary TaskItem and transfer progress without
  corrupting occurrence fields.
- Directory/cross-Storage/multi-item transfer execution is still performed synchronously inside
  the mutation HTTP request: `MediaFlowApi` calls `execute_transfer`, which creates the Task and
  immediately calls `_run_transfer_task` before returning. There is no queued/claimed resident
  worker boundary, so the Web receives no durable identity until all Storage work finishes and can
  show only a request spinner plus the terminal response; the new pause test requests pause from a
  Storage callback inside that same request, and the Web has no progress polling or usable resume
  action. A same-Storage single-file process loss also leaves a `files_direct_command` Task in
  `RUNNING`/`PROCESSING` with no transfer continuation path. Move long work behind genuine durable
  Task admission/claim/fencing so the request returns the Task identity immediately, persist safe
  per-entry/checkpoint progress, and make Files show/poll progress and expose the advertised safe
  continuation or investigation action without raw-ID ceremony. Add API/Web and restart tests that
  prove this actual asynchronous journey rather than callback-injected pause inside a synchronous
  call.
- Mixed entry outcomes inside one top-level directory are still collapsed to fabricated success.
  B's direct reproduction of `_item_status([SUCCESS-with-CREATE_DIRECTORY, SKIPPED])` returns
  `SUCCESS`; `_run_transfer_task` consequently persists the whole TaskItem/Result as successful and
  reports its known effect as `transferred`, despite a child being skipped. Aggregate any mixed
  success/skipped directory outcome as `PARTIAL`, retain the skipped child evidence, and add a
  directory regression where the root is created but a child encounters a late conflict under
  `SKIP`, proving response, TaskItem, Result and reloaded detail all remain truthful.

## Same-Task Correction Plan — 2026-09-17

This plan remains inside Task 37.4. It does not change the Task ID, Task Base, Goal, parent Slice,
original Acceptance Criteria or Non-goals. The Developer must correct all three blockers in one
coherent checkpoint and return this same Task to `READY FOR B REVIEW`.

### 1. Make schema 35 TaskItem persistence upgrade-safe

- Replace every positional `INSERT INTO task_items VALUES (...)` path with an explicit, identical
  column list. Cover ordinary upsert, atomic TaskItem/Result completion, manual-execution completion
  and every other alternate insert path; do not fix only the transfer-specific caller.
- Keep `_item_values` and `_item` semantically aligned with the named columns, but do not depend on
  their physical SQLite order. A fresh schema 35 database and a schema 34 database upgraded in
  place must produce the same loaded `PersistentTaskItem` values.
- Preserve existing occurrence identity. Migration and later writes must not move, overwrite or
  reinterpret `source_occurrence_id`, `source_fingerprint` or
  `source_fingerprint_state`; non-transfer TaskItems must continue to store `progress = NULL`.
- Add an isolated 34 -> 35 migration fixture whose schema-34 `task_items` layout already contains
  the occurrence columns. Initialize it through the production repository migration, then prove:
  an ordinary TaskItem can be inserted and reloaded; a transfer TaskItem can persist/reload bounded
  progress; pre-existing occurrence fields survive unchanged; terminal completion clears progress
  without corrupting occurrence or Result evidence.
- Inspect all `task_items` insert statements after the correction and add a regression assertion or
  helper that prevents a later caller from reintroducing physical-column-order dependence.

### 2. Split durable transfer admission from execution

- Refactor the transfer command into two explicit application boundaries:

  ```text
  impact/read-only admission
  -> exact submitted manifest revalidation
  -> atomically persist PENDING Task + bounded per-item transfer authority
  -> return durable operator projection immediately
  -> resident Worker claims under a persisted fence
  -> per-entry OrganizerExecutor execution and durable progress
  -> terminal TaskItem/Result projection
  ```

- For directory, cross-Storage and multi-item work, the mutation HTTP request must not call
  `_run_transfer_task` inline. It returns only after durable admission, before the first Storage
  mutation, with an ordinary Files-facing state that the Web can follow without exposing a raw
  token or requiring Task-ID copy/paste.
- Persist enough bounded authority before returning to reconstruct the exact confirmed operation
  after process restart: pinned configuration revision/digest, source/destination ResourceLibrary
  and Storage identities, normalized logical paths, operation, conflict choice, confirmed entry
  scope and pinned keep-both destinations. Do not persist host roots, credentials, provider payloads
  or content.
- Execute through the existing resident Worker ownership model or an equivalent existing durable
  Task runner with atomic claim, lease/fence and compatible-snapshot checks. The API process must not
  create or supervise an implicit worker. Only the current claim owner may advance progress or
  publish a terminal result.
- Persist progress after each safe entry or compound checkpoint. Pause/cancel must be requested via
  the normal authenticated Task lifecycle API and observed at a safe boundary; completed effects
  remain terminal. Resume must enqueue/claim the same persisted authority and must not execute the
  remaining transfer synchronously inside the resume HTTP request.
- On process loss, a replacement Worker may continue only from a persisted known-safe checkpoint.
  Missing, truncated, stale or uncertain authority becomes a durable
  `transfer_interrupted`/investigation outcome with the exact known effects and next action; it is
  never blindly replayed.
- Prefer routing the permitted same-Storage single-file fast path through this same durable runner
  so Copy/Move has one recovery model. If the inline optimization is retained, it must atomically
  reach a truthful terminal state or be recoverable after process loss; it may not leave a
  `files_direct_command` Task indefinitely `RUNNING`/`PROCESSING` with no supported continuation or
  investigation transition.
- Update Files to retain the source ResourceLibrary, directory, destination, conflict choice and
  unaffected selection after admission. Poll or otherwise read the bounded transfer projection and
  show queued/running/paused/cancelled/completed/partial/uncertain per-item state, known checkpoints
  and the backend-advertised safe next action. Provide pause/cancel/resume or investigation actions
  only when the backend lifecycle projection advertises them; do not expose execution tokens or
  require the operator to copy a Task ID.
- Keep all mutation in `OrganizerExecutor`, preserve same-Storage native-only behavior and the
  explicit cross-Storage Copy -> verify -> Delete-source boundary, and retain current Active
  snapshot, RBAC, confinement, conflict and no-uncertain-replay rules across Worker reconstruction.

### 3. Make nested mixed-outcome aggregation truthful

- Define one deterministic per-item status precedence used by response, TaskItem, Result and reloaded
  detail:

  ```text
  any UNCERTAIN                      -> UNCERTAIN
  all SUCCESS                        -> SUCCESS
  all SKIPPED                        -> SKIPPED
  SUCCESS + SKIPPED                  -> PARTIAL
  any known mutation + FAILED/PARTIAL -> PARTIAL
  failure with zero known mutation   -> FAILED
  ```

- Count directory creation and removal, file Copy/Move and skipped children in that same aggregate.
  A created destination directory plus a skipped child is a partial item, not a completed transfer.
- Persist the exact skipped child and completed directory/file checkpoints in bounded Result
  evidence. The top-level known effect must be `partial`, aggregate counts must not increment the
  wholly transferred count, and reloaded Task/Result detail must reproduce the same state.
- Keep Web selection pruning tied to physical source truth rather than the aggregate label: Copy
  retains the source selection; Move clears only a source whose known effect proves it is gone;
  skipped, partial and uncertain sources remain selected or are refreshed before any pruning.

### Correction Acceptance and Required Tests

- A production-shaped schema 34 -> 35 migration test passes for ordinary, transfer-progress and
  terminal TaskItem writes, and verifies unchanged occurrence fields. Run the repository's existing
  migration/upgrade regression group in addition to the Task's original T4 commands.
- A blocking/fault-injecting Storage test proves a long transfer submission returns a durable Task
  identity before the first mutation completes. A separately invoked Worker claim advances it;
  execution does not occur on the API request stack.
- API lifecycle tests pause and cancel a genuinely running directory transfer from a separate
  request, then prove a permitted resume is worker-driven and never replays completed or uncertain
  entries. Do not satisfy this criterion by making the Storage callback mutate Task rows itself.
- Restart tests cover process loss before mutation, after one safe entry, after destination Copy,
  after verification and around source deletion. Each case either continues from persisted safe
  authority or stops in an actionable investigation state; no completed/uncertain mutation is
  repeated.
- A same-Storage single-file process-loss test proves the selected implementation cannot leave an
  indefinitely running, non-continuable Task.
- One bounded directory test creates the destination root successfully, introduces a child conflict
  after admission and applies `SKIP`; response, durable TaskItem, Result, reloaded detail and Web
  presentation must all report partial completion and retain the skipped child evidence.
- Web tests prove immediate admitted/running state, bounded progress refresh, backend-advertised
  pause/cancel/resume or investigation action, context preservation and duplicate-submit
  prevention. The ordinary flow must not require a raw Task ID or internal checkpoint value.
- Rerun every original Task 37.4 T4 command and report exact totals, skips and unavailable external
  gates. The three previously reported full-suite failures may be treated as unrelated only if they
  are reproduced unchanged at the Task Base; no assertion, migration test, Worker safety test or
  private-file check may be removed, weakened or hidden.

## Prior B Review Result — 2026-09-17 (superseded by the review below)

```text
Reviewed: 4954502c6493d57634a14461a7268120419319da..1cc414b4f12f54b0f2db4aeb4fa17ac7f7876510
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The lease keeper still permits concurrent duplicate mutation after a transient ownership-signal
  failure. Its thread exits permanently on the first `False` return or exception from
  `heartbeat_files_transfer_claim`; the already-entered provider call continues, while the ordinary
  expired-lease query may hand the same `RUNNING` transfer to another Worker. B injected one failed
  keeper heartbeat while Worker A was blocked inside native Copy, waited past the one-second lease,
  then polled Worker B: before releasing Worker A, `mutation_calls=2` and the durable owner had
  changed to Worker B. Both threads subsequently completed and the transfer reported `completed`.
  This still violates the no-duplicate Copy/Move/Delete invariant and the correction requirement
  that takeover occur only after the previous mutation owner is genuinely gone. Make an expired
  in-flight mutation non-claimable unless prior ownership/effect is safely resolved (or use an
  equivalent durable fencing/idempotency design); a heartbeat fault must never convert a live,
  blocked mutation into replayable work. Add the failed/exceptional-heartbeat two-Worker regression,
  not only the happy-path keeper regression.
- Worker failure convergence still publishes contradictory aggregate truth after a known effect.
  B admitted one Copy, claimed it, persisted one `SUCCESS` entry checkpoint, then invoked
  `converge_worker_failure`: the resulting state was
  `transfer=failed, task=failed, item=partial, result=partial, Files projection=PARTIAL`. The cause is
  `_converge_execution_failure`, which counts converted unfinished items only as failures and chooses
  `PARTIAL_SUCCESS` only when another item was already completed. A no-mutation probe also persisted
  `effect_certainty=verified_complete` for a failed item with no completed operation, rather than
  `none`. Apply the required deterministic precedence consistently to transfer, Task, TaskItem,
  Result, Files and Operations projections: known mutation plus later failure is `PARTIAL`; an error
  before mutation is `FAILED` with no-effect evidence; an unprovable effect is `UNCERTAIN`. Add
  fault-injection coverage that actually fails after a persisted known effect and around terminal
  publication/reload. The current `_ExplodingCopySource` raises before performing Copy and its test
  accepts any of `FAILED/PARTIAL/UNCERTAIN`, so it does not prove this requirement.
- The required cross-boundary and pinned-revision regressions remain incomplete. The claimed
  “real-admission fixture” is a hand-copied TypeScript object in
  `web/src/entities/library/direct-files.test.ts`; no Python API response fixture is consumed by the
  TypeScript normalizer, so the Python/TypeScript shape can drift exactly as it did before. The
  resident-Worker tests cover a newer Worker reconstructing an older pin and a factory returning
  `None`, but do not cover the reported old-process/newer-admission direction, simultaneous older and
  newer pinned queued transfers, or corrupt pinned authority/runtime reload. Add the explicitly
  required cross-boundary admission check and both-direction resident-Worker activation/recovery
  tests against the production-shaped reconstruction path.

### Required same-Task correction direction

The Developer must resolve the three blockers above in this Task. The following direction clarifies
the required safety and acceptance boundary; it does not change the Task ID, Task Base, Goal,
Implementation Scope, original Acceptance Criteria or Non-goals.

#### 1. Make in-flight mutation ownership non-replayable

- Persist an explicit distinction between a claim that has not entered a Storage mutation and an
  operation that may currently be in flight. An expired pre-mutation claim may be reclaimed; an
  expired in-flight Copy/Move/Delete/CreateDirectory/Write or source-directory removal may not be
  selected by the ordinary claim query merely because its lease time elapsed.
- Before each `OrganizerExecutor` mutation, atomically publish the exact item/entry and
  `mutation_in_flight` boundary under the current claim token. Only that owner may publish the
  corresponding verified checkpoint and return the entry to a continuation-safe state.
- If the owner disappears while an operation is in flight and the provider cannot prove the exact
  effect or offer a genuinely idempotent/fenced continuation, converge the entry to durable
  `UNCERTAIN`/investigation-only state. Do not automatically invoke the operation again. A known-safe
  checkpoint before the next mutation remains reclaimable and may continue from that checkpoint.
- Keep the lease keeper as liveness support, but do not use successful heartbeat delivery as the
  sole data-integrity fence. A transient `False`, SQLite error or keeper-thread failure must be
  observable and retried/bounded, and must never make an already-entered mutation replayable. Claim
  token CAS remains mandatory for every progress, TaskItem, Result, Task and terminal publication.
- Apply the same boundary to source-directory cleanup. Pause/cancel may stop before the next
  mutation; they cannot relabel an in-flight or unknown effect as safely retryable.
- Add two-Worker fault tests for keeper heartbeat returning `False` and raising while Worker A is
  blocked inside Storage. Worker B must perform zero mutation. Also cover owner loss before the
  mutation boundary (safe takeover), after a verified checkpoint (continue from the next entry),
  and during mutation (terminal investigation with no replay).

#### 2. Use one post-convergence aggregate and effect-certainty model

- Build one pure deterministic aggregate from the **post-conversion** TaskItem/Result evidence and
  use it for the transfer row, Task row, Files projection and Operations detail. Do not calculate
  the Task/transfer aggregate from the stale pre-conversion item list.
- Preserve this precedence exactly:

  ```text
  any UNCERTAIN                         -> UNCERTAIN
  all SUCCESS                           -> SUCCESS
  all SKIPPED                           -> SKIPPED
  SUCCESS + SKIPPED                     -> PARTIAL
  any known mutation + FAILED/PARTIAL   -> PARTIAL
  failure with zero known mutation      -> FAILED
  ```

- Map effect certainty independently from outcome wording: zero attempted mutation is `none`; a
  verified known effect is `verified_complete`; an operation whose effect cannot be proved is
  `attempted_unverified`. Preserve bounded completed operations/checkpoints in the terminal Result
  instead of clearing the evidence that caused the aggregate decision.
- Keep failure convergence atomic and idempotent. Repeating terminal convergence or reloading after
  any commit boundary must reproduce the same status, counts, effect certainty, retry safety and
  next action without creating an additional Result.
- Replace permissive assertions such as `FAILED/PARTIAL/UNCERTAIN` with exact scenario assertions.
  Cover failure before the first mutation, after one persisted verified effect, during an
  unprovable provider effect, after one successful sibling, and immediately before/after terminal
  publication. Assert transfer, Task, every TaskItem, Result, Files projection and Operations detail
  agree after repository reload.

#### 3. Bind the admission and pinned-runtime tests across real boundaries

- Create one shared, committed, secret-free admission contract fixture (or an equally strong
  generated/integration contract). A Python API test must produce the real admitted response and
  compare it to that fixture; the TypeScript normalizer and Files fake server must consume the same
  fixture. A separately hand-written object in each language is not cross-boundary evidence.
- The shared contract must assert exact `topLevelPaths: string[]`, destination pairs, queued Task
  state, bounded item outcomes and absence of host paths/credentials. The Files interaction test
  must still prove one submit enters queued polling, retains source/destination/conflict context and
  cannot submit again after admission committed.
- Exercise the production-shaped resident Worker reconstruction path in both directions: a Worker
  process composed under revision A executes work admitted under later revision B, and a Worker
  composed under B executes still-queued work pinned to A. Queue both revisions together and prove
  each transfer uses only its own ResourceLibrary/Storage bindings and digest.
- Cover missing revision, digest mismatch, corrupt authority JSON and runtime reconstruction
  failure. An incompatible Worker must invoke no `OrganizerExecutor` mutation, must not mark valid
  work as a business failure, and must leave bounded queued/readiness or investigation evidence for
  a lawful Worker/operator action. A compatible later Worker must complete only from the persisted
  pin and safe checkpoint.

#### Correction acceptance evidence

- The failed-heartbeat two-Worker probe records one and only one Storage mutation and no takeover
  while the first mutation may still be in flight.
- Known-effect failure records `PARTIAL` consistently across transfer, Task, TaskItem, Result, Files
  and Operations; pre-mutation failure records `FAILED` with `effect_certainty=none`; unknown effect
  records `UNCERTAIN` and exposes investigation only.
- The Python-produced admission document is consumed by the TypeScript contract test, and both
  old-to-new and new-to-old resident Worker revision cases pass through production-shaped runtime
  reconstruction.
- Rerun the complete original Task 37.4 T4 command list and report exact totals, skips, reproduced
  unrelated baseline failures and unavailable external gates. Do not weaken or delete an existing
  mutation, migration, Worker, Web or private-file assertion.

## B Review Result

```text
Reviewed: 4954502c6493d57634a14461a7268120419319da..042670872f3bd2e03706c721871f7daa11d16d9c
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- `begin_item(..., transfer_fence=..., adopt_existing=True)` writes the `PROCESSING` TaskItem with
  an unguarded `repository.upsert_item(item)` **before** `adopt_or_acquire` validates the claim and
  rotates the lock. B reproduced a stale Worker A after Worker B had taken the claim, rotated the
  source lock and persisted `progress={"owner":"worker-b"}`: A correctly raised `TaskClaimLost` and
  did not steal B's lock, but it had already changed the durable item from
  `before_progress={"owner":"worker-b"}, before_attempts=1` to
  `after_progress=None, after_attempts=2`. This lets a lost claimant erase the current owner's safe
  recovery checkpoint and contradicts the claim-fenced TaskItem contract.

  Required correction for this same Task:

  1. Treat transfer-item admission as one claim-fenced ownership boundary. The live transfer claim,
     same-Task lock adoption/acquisition and TaskItem start publication must be ordered so no
     TaskItem write can occur before ownership is proven. Prefer one repository transaction when
     practical. An equally strong two-step implementation may acquire/rotate the exact lock
     generation first and then use `upsert_item_guarded`, but if the guarded publish fails it must
     release only that exact generation and raise `TaskClaimLost`; it must never perform an
     unguarded compensating write.
  2. Apply the fence to **every** transfer-path TaskItem write, including the initial
     `PROCESSING`/attempt update and the lock-conflict `FAILED` update. A claim may be lost between
     any two calls, so a separate unguarded write after a successful claim check is not sufficient.
     A stale claimant must leave TaskItem, Result, transfer mutation boundary and replacement lock
     generation byte-for-byte/semantically unchanged and must invoke no Storage mutation.
  3. Increment `attempts`, change `status`/`stage`/`updated_at`, or publish a lock failure only after
     the exact Worker has successfully crossed the guarded ownership boundary. A failed or stale
     acquisition must not consume an attempt or fabricate a user-visible business failure.
  4. Preserve the last durable progress/checkpoint while starting a valid continuation. Do not
     replace a resumable TaskItem with a new `progress=None` row merely because its replacement
     Worker entered `begin_item`. If that Worker crashes after acquisition but before its first new
     checkpoint, the next lawful Worker must still reconstruct the prior safe continuation rather
     than degrading to `files_transfer_interrupted_unknown`. Supersede the old checkpoint only with
     a later claim-guarded progress or terminal publication.
  5. Keep the round-7 gap-free lock properties: same-Task handoff remains an in-place rotation, a
     different Task's row fails closed, a predecessor's late release is an exact no-op, and an
     unprovable in-flight mutation is never handed off. Do not reintroduce blanket
     `reclaim_task_locks` on the production takeover path and do not add a new persistent lifecycle
     state to solve this ordering problem.
  6. Cover lost ownership at all relevant boundaries: before Task-wide rotation, between Task-wide
     rotation and per-item adoption, after per-item adoption but before TaskItem start publication,
     and after start publication but before the next progress write. Every case must stop before the
     next mutation and preserve the current owner's durable evidence.

  Required regression evidence:

  - Add the deterministic two-claim reproduction above. After B owns the claim, exact lock
    generation and a distinctive durable checkpoint, invoke A's stale continuation and assert
    `TaskClaimLost`, zero Storage mutation, no new Result, B's lock still owned, and equality of B's
    TaskItem `status`, `stage`, `attempts`, `progress`, error and recovery-relevant fields.
  - Add a valid-continuation crash-window regression: B adopts an existing resumable checkpoint and
    stops immediately after the guarded start boundary but before publishing new progress; after a
    repository reload, C must reconstruct the original safe checkpoint and continue without replay
    or investigation-only degradation.
  - Retain the real A/B/C production takeover and direct handoff-interleaving regressions. They must
    continue proving that Task C is denied before and after A returns and that only the current
    owner's terminal release frees the path.
- The new production takeover regression weakens the former exact terminal assertion from
  `status == "completed"` to `status in {"completed", "partial_success"}`, despite this Task's
  explicit prohibition on weakened safety assertions. B ran the scenario and observed
  `OBSERVED_TERMINAL_STATUS=completed`. Restore the exact `completed` assertion and prove the
  transfer row, Task row, every TaskItem, Result, Files projection and Operations detail agree after
  repository reload. Do not replace it with a set-membership assertion, conditional assertion or
  hidden skip. Then rerun and report the complete original Task 37.4 T4 command list with exact
  totals, skips, genuinely reproduced Task-Base failures and unavailable external gates.
