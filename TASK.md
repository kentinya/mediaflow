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
safety** and **RO-9 Actionable recovery** by delivering the complete Web-native Copy and Move
journey for one item or a bounded selection of files/directories. An authorized operator chooses an
explicit destination inside an enabled Active ResourceLibrary, sees truthful capability/conflict and
compound-transfer behavior, and receives independent durable outcomes without media-organize
ceremony, silent fallback, silent replacement or unsafe source deletion.

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
continuity and FileIndex reconciliation likewise remain separate because they use the existing
Preview/intent/result authority rather than this direct transfer command.

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
  command depends on exact identity; if the provider cannot prove the required boundary, fail
  closed with an actionable reason. Do not weaken Task 37.3's Rename/Delete evidence contract or
  treat size/`mtime` alone as authority for destructive source deletion.
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

## Non-goals

- Upload, Download, browser multipart/resumable upload, response/archive streaming or transfer to
  arbitrary host paths.
- Media recognition/metadata/naming/classification, a new organize Planner, multi-item media
  Organize completion, terminal Organize-to-FileIndex reconciliation or broad FileIndex repair.
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
