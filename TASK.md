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

> Correction round 2026-09-17: the report below covers the F-1..F-6 correction
> checkpoint; the superseded first-round report content has been replaced. The
> correction commit sits after the original Task 37.4 checkpoint
> `9eafe9e3fef11e993670b42b762d747cbc0dee5a` without amending it.

### Changed Files

- `mediaflow/domain/direct_files.py` — `MAX_TRANSFER_PROGRESS_ENTRIES` bound
  (the durable per-item confirmed-scope/progress cap).
- `mediaflow/domain/task_persistence.py` — `TRANSFER_INTERRUPTED_STAGE` and the
  bounded in-flight transfer `progress` field on `PersistentTaskItem`.
- `mediaflow/infrastructure/sqlite_runtime.py` — runtime schema 35: additive
  `task_items.progress` column (CREATE TABLE + ALTER migration) and the
  reordered `_item_values`/row mapping that persist it.
- `mediaflow/application/task_runtime.py` — `complete_direct_item` now persists
  the exact destination Storage identity, the bounded per-entry checkpoint
  annotations, an optional interrupted stage and `SKIPPED` status;
  `record_transfer_progress` persists the bounded in-flight authority (operation,
  conflict mode, endpoint identities, confirmed per-entry scope, recorded entry
  outcomes, exact aggregate counters).
- `mediaflow/application/direct_file_commands.py` — one cached adapter instance
  per configured Storage identity for the whole pinned-snapshot service
  lifetime (F-2), so no business decision depends on incidental object identity.
- `mediaflow/application/organizer.py` — `execute_direct_copy/move` accept an
  explicit validated `same_storage` decision (object identity stays only as the
  conservative fallback); `verify_streamed_copy` recovery evidence primitive;
  `_cross_storage_move` accepts a `verified_destination` continuation that
  adopts the persisted Copy/verify checkpoints instead of re-copying.
- `mediaflow/application/direct_file_transfers.py` — the F-1..F-5 core:
  `_TransferPlan`/`_ResumeContext` execution model; the selected conflict mode
  now binds every top-level AND directory destination with fresh last-boundary
  revalidation (a conflicting directory is never merged, a directory Move
  removes no source when the item must fail or skip); in-batch destination
  collisions are detected at impact (`batch_conflict`) and reported per sibling
  at execution (deterministic sorted order); keep-both names are pinned against
  batch-assigned destinations too; destination-state checks resolve through the
  destination ResourceLibrary root (latent wrong-root bug found by the new
  nested-root fixtures); truthful per-item aggregation (`_item_status`) that
  includes directory creation/removal outcomes and `SKIPPED`; `SKIPPED` items
  persist as `TaskItemStatus.SKIPPED`; per-entry pause/cancel observation with
  bounded durable progress snapshots; `resume_transfer` continues a paused or
  interrupted transfer Task only from its persisted known-safe checkpoint
  (confirmed-scope match required, completed entries never replayed, uncertain
  effects never continued, keep-both never re-derived, RUNNING refused,
  stale-Active refused) with a verified-destination continuation of an
  interrupted compound Move and explicit investigation states for items
  without a usable checkpoint; `_transfer_status` gains truthful SKIPPED and
  mixed-batch states and `itemOutcomes`/`skippedItems` in the response.
- `mediaflow/interfaces/service_api.py` — `POST /api/v1/tasks/{id}/resume` now
  continues `files_transfer` Tasks through the same application service while
  every other command keeps its actionable refusal.
- `web/src/entities/library/direct-files.ts` — optional `skippedItems` on the
  transfer result model.
- `web/src/features/library/TransferDialog.tsx` — the impact fetch is part of
  one submission (duplicate-submit window closed); the result view shows
  skipped/mixed aggregates, bounded per-entry outcomes with known-state
  explanations (including the verified-copy/source-retained compound state)
  and truncation notes.
- `web/src/features/library/StorageFilesPage.tsx` — transfer success pruning
  distinguishes Copy from Move: only a Move whose known effect proves the
  source is gone clears the selection.
- Tests: `tests/test_direct_file_transfers.py` (+17 tests: directory/in-batch
  conflict intent, production-factory and explicit same-Storage decisions,
  resolved-root overlap, aggregation truth, durable Result identity, durable
  pause/resume/interruption), schema-pin fixtures updated for runtime schema
  35 (`tests/test_configuration_organize.py`, `test_configuration_classification.py`,
  `test_configuration_destination.py`, `test_configuration_destination_activation.py`,
  `test_configuration_destination_precheck.py`),
  `web/src/features/library/StorageFilesPage.test.tsx` (+3).

### Implemented

- F-1: the selected conflict mode now applies to every top-level and directory
  destination with fresh last-boundary revalidation. A directory `MOVE` with
  `FAIL` performs zero mutation for that item (the B reproduction now returns
  `FAILED`, the complete source stays, nothing merges); `SKIP` records a
  truthful skipped item; `KEEP_BOTH` pins one unique root and every descendant
  beneath it; in-batch destination collisions are detected at impact and
  reported deterministically per sibling instead of merging.
- F-2: the same-Storage decision is the validated configured-Storage-identity
  decision (adapter cache per pinned snapshot plus an explicit executor
  argument); the production-style factory path is proven to invoke only native
  `Storage.copy`/`Storage.move` with zero streaming/Delete fallback; overlap
  checks compare fully resolved logical Storage paths across ResourceLibrary
  roots (a latent destination-root resolution bug found by these tests is
  fixed).
- F-3: `SKIPPED` persists as `TaskItemStatus.SKIPPED` with a skipped known
  effect; destination-directory creation/removal participates in aggregation;
  a failed emptied-source removal is an uncertain/partial item, never a wholly
  successful directory Move; all-skipped/mixed/partial/uncertain aggregates are
  truthful; the Web prunes selection only for a Move and keeps it after a Copy.
- F-4: the durable Result and TaskItem now carry the exact destination
  Storage/ResourceLibrary identity, logical source/target, bounded per-entry
  checkpoint annotations and effect certainty; Task/Result detail reloads
  reproduce the truthful state without the original response.
- F-5: directory, cross-Storage and multi-item transfers observe pause/cancel
  at every per-entry boundary; each item persists a bounded progress authority
  (confirmed per-entry scope, endpoint identities, recorded outcomes); a new
  `resume_transfer` continues only from that persisted known-safe checkpoint,
  stops with explicit interrupted/investigation states otherwise, never
  replays completed or uncertain effects, and is reachable through the
  existing Task lifecycle route; a short same-Storage single-file command
  keeps the identical persistence/audit/executor semantics.
- F-6: the transfer dialog closes the duplicate-submit window during impact
  acquisition, shows bounded per-item progress/outcomes with a known-state
  explanation and the safe next action, and preserves destination/conflict
  input on recoverable failure; selection pruning distinguishes Copy from
  Move.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS; `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `test -z "$(grep -rn -i -E 'ffprobe|ffmpeg' mediaflow pyproject.toml)"`
  (rg unavailable in this environment; equivalent grep) — PASS, no matches.
- `.venv/bin/python -m unittest tests.test_direct_file_transfers` — PASS (38).
- `.venv/bin/python -m unittest tests.test_direct_file_operations` — PASS (55).
- `.venv/bin/python -m unittest tests.test_source_directory_cleanup
  tests.test_manual_organize_execution tests.test_configuration_organize` — PASS.
- `.venv/bin/python -m unittest tests.test_organizer
  tests.test_organizer_mutation_authority tests.test_organizer_rollback` — PASS (45).
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage
  tests.test_openlist_storage tests.test_s3_storage` — PASS (94).
- `.venv/bin/python -m unittest tests.test_runtime_files_browser
  tests.test_api_security tests.test_task_persistence
  tests.test_task_pause_resume tests.test_task_retry` — PASS.
- `.venv/bin/python -m unittest discover -s tests` — 1637 tests: FAIL with only
  the same 3 failures reproduced identically at a clean Task Base worktree
  (`4954502`, see Risks); all schema-version fixture pins updated for runtime
  schema 35.
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE, same
  environment limitation as the first round: the Docker daemon rejects the
  smoke harness's bind mounts (`bind source path does not exist:
  /tmp/mediaflow-smoke-security-*/…`); the script fails visibly, nothing is
  hidden or asserted as PASS.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` — PASS;
  `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS
  (SHA-256 641763b8…); wheel artifacts removed after the check.
- `cd web && npm run format:check` — PASS; `npm run typecheck` — PASS;
  `npm run lint` — PASS.
- `cd web && NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx`
  — PASS (32; the required `npx vitest run` invocation needs `NODE_ENV=test`
  in this shell, otherwise vitest resolves the production React build and
  every jsdom test errors with `React.act is not a function` — an environment
  invocation detail, reported as observed).
- `cd web && npm run test -- --run` — PASS (33 files / 451 tests).
- `cd web && npm run build` — PASS.
- `cd web && npx playwright test tests/e2e/library-files.spec.ts
  --project=chromium` — PASS (28); `npm run test:e2e` — PASS (106).
- `git diff --check` — PASS; staged manifest inspected: no
  `config/alist.json`, credentials or unrelated files; the pre-existing dirty
  `docs/pics/文件页.png` is preserved and deliberately not staged.

### Decisions

- The correction uses one coherent execution model (`_TransferPlan`) instead
  of patching the old manifest-driven loop: both fresh execution and durable
  continuation drive the same per-entry admission, conflict and progress
  semantics, so a resumed Task cannot diverge from a freshly confirmed one.
- The durable continuation authority is the per-item bounded progress
  snapshot (runtime schema 35, `task_items.progress`): confirmed per-entry
  scope plus endpoint identities plus recorded outcomes.  An item without a
  persisted known-safe checkpoint becomes an explicit interrupted/investigation
  state (`transfer_interrupted`, `files_transfer_interrupted_unknown`) and is
  never blind-retried; keep-both continuations are refused because their
  unique names were admission-pinned and cannot be re-derived.
- A cross-Storage Move interrupted after the Copy is continued by
  digest-verifying the existing destination (`verify_streamed_copy`) and
  finishing only the destructive source step with fresh exact evidence
  (`verified_destination=True`); a truncated/foreign destination falls through
  to the selected no-overwrite conflict behavior instead of being overwritten
  or deleted.
- Mixed skip/success aggregates report PARTIAL (not fabricated SUCCESS);
  all-skipped reports SKIPPED; the per-item known effects stay exact either
  way.  A failed emptied-source-directory removal surfaces the executor's
  uncertain delete certainty as an uncertain item — it is never reported as a
  wholly successful directory Move.
- The same-Storage decision is enforced at two layers (per-snapshot adapter
  cache and the explicit executor argument) so neither the service nor the
  executor can silently drift back to object identity.
- Destination-state checks now resolve through the destination ResourceLibrary
  root; this latent wrong-location bug was invisible while every fixture
  library sat at a Storage root and is a direct root cause of truthful
  conflict revalidation (F-1 family).
- `TASK.md` (B's correction text plus this report) travels with the
  correction checkpoint per the workflow; `docs/pics/文件页.png` remains
  unstaged/dirty.

### Remaining In-Slice Work

- Upload and Download journeys (browser multipart/resumable upload, bounded
  streamed archive download) are untouched by this Task.
- The remaining media-Organize/FileIndex reconciliation journey: multi-item
  Organize completion from Files, terminal Organize-to-FileIndex reconciliation.
- Web-side resume affordance: the durable transfer continuation is reachable
  through the Task lifecycle API (`POST /api/v1/tasks/{id}/resume`); whether
  the V2 Task detail should surface a resume control for `files_transfer`
  Tasks is B's call.

### Risks / Deviations

- Full-suite FAIL is limited to the same 3 failures already present at the
  Task Base (`test_configuration_status.ConfigurationSnapshotTests.test_hostile_configuration_content_is_never_exposed`
  and the two
  `test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_*`
  golden-fixture failures asserting 201). Reproduced at a clean Task Base
  worktree before judging this correction; pre-existing and unrelated to this
  Task, and the B PASS judgment on them is not mine to make.
- The Docker release-security gate remains UNAVAILABLE in this workspace
  (daemon rejects the smoke context bind mounts); it needs a host where Docker
  can bind-mount the smoke context.
- Runtime schema 34 → 35 is an additive migration (`task_items.progress`);
  legacy rows read `None` and behave exactly as before.  Five test modules pin
  the schema version and were updated with the bump; no safety assertion was
  removed, weakened or skipped.
- Per-item durable progress stores the confirmed entry scope bounded at
  `MAX_TRANSFER_PROGRESS_ENTRIES` (512); an item whose confirmed scope is
  larger cannot be safely continued after an interruption and stops with an
  actionable `files_transfer_resume_scope_changed` state — a bounded,
  documented limitation of the recovery authority, not silent scope expansion.
- Vitest must run with `NODE_ENV=test` in this shell (see Tests and Results).

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: PENDING_COMMIT
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

## B Review Result

```text
Reviewed: 4954502c6493d57634a14461a7268120419319da..9eafe9e3fef11e993670b42b762d747cbc0dee5a
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: Developer corrects Task 37.4 in the same correction loop; Task 37.5 is not active.
```
