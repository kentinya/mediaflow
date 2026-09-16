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
per-entry cleanup effects without production services.

## Non-goals

- Upload, Download, browser multipart/resumable upload, response/archive streaming or transfer to
  arbitrary host paths.
- Media recognition/metadata/naming/classification redesign, a new organize Planner, multi-item
  media Organize completion, terminal Organize-to-FileIndex reconciliation or broad FileIndex
  repair. Only the existing `sourceDirectoryCleanup` Move continuation described above is in scope.
- New Storage providers, adapter-wide redesign, invented provider capability, implicit transfer
  fallback, unbounded recursion/batches or distributed transfer workers.
- Reopening or weakening Task 37.3 Rename/Delete exact-entry evidence, bounded text Save semantics,
  ResourceLibrary managed removal or any accepted safety test.
- Broad non-Files body redesign, V1 cutover, optional copy polish, P2/P3 cleanup or work outside
  Slice 37.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: NOT STARTED
Head SHA: NOT SET
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
