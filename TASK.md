# Task 38.3 — 完成 MediaLibrary 有界直接文件维护

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.3
Parent Slice: 38
Status: READY FOR B REVIEW
Task Base: fabdb35373038ef36dd8b558688b2bce53ddcc89
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authorized operator can perform the bounded, ordinary maintenance actions supported by the
MediaLibrary Files page: create a folder, create a supported text file, rename one entry, open and
save supported text, and delete selected entries. Every action is scoped to the exact enabled
MediaLibrary in the current Active configuration, uses the existing safe direct-file execution
boundary, reports durable per-item outcomes, and provides a Web recovery path. This advances Slice
38 RO-5 and the MediaLibrary mutation portion of RO-7 while preserving the completed browse and
configuration journeys from Tasks 38.1 and 38.2.

## Why This Task Exists

Task 38.1 delivered a live, read-only MediaLibrary browser and Task 38.2 delivered page-local
MediaLibrary configuration. The page still cannot maintain the files that an operator sees, so the
main ordinary MediaLibrary journey stops after inspection. The repository already has bounded
ResourceLibrary direct-file admission, evidence, OrganizerExecutor mutation, task/result and Web
dialog patterns; the next coherent unit is to extend those mechanisms with an independent
MediaLibrary authority rather than duplicate or relabel ResourceLibrary IDs.

This Task is intentionally limited to the non-transfer direct commands. Copy/Move between
MediaLibraries needs its own cross-endpoint resolution, verification, durable transfer and Worker
recovery review; it is not required to make this Task independently useful and remains a later
Task.

## Implementation Scope

```text
Domain / direct-command application
  → MediaLibrary-scoped persistence and exact-Active admission
  → API
  → Web client, dialogs and page actions
  → focused, integration and browser tests
```

- Extend the existing direct-file command boundary so Create Folder, Create supported Text File,
  single-item Rename, bounded supported-text Open/Edit/Save and Delete resolve an enabled
  MediaLibrary from the exact immutable Active snapshot. Client-supplied Storage IDs, host roots
  and arbitrary paths are never runtime authority.
- Add MediaLibrary-scoped API surfaces matching the existing direct-command behavior for:
  command admission/execution, text read/save, delete impact and rename evidence. Use the
  `/api/v1/media-libraries/{id}/files/...` namespace and preserve ResourceLibrary route and
  response compatibility. Enforce the same authenticated permissions, path confinement, provider
  capability checks, entry type/size limits, current-version evidence and conflict rules in API and
  Web.
- Route every Storage mutation through `OrganizerExecutor`. Reads, impact/evidence calculation,
  text opening and configuration lookup remain zero-mutation and do not invoke Scanner, Parser,
  Recognition, Metadata, Naming, Classification or media Organize.
- Preserve direct-command safety semantics: no silent overwrite/delete, explicit Delete
  confirmation, no batch Rename, supported text extensions only, bounded text size, no arbitrary
  binary/image/video editing, no implicit capability fallback, and no automatic replay after an
  uncertain transport or mutation result.
- Record and expose bounded per-item outcomes and known effects using the existing direct-command
  task/result model. Completed, failed, partial and uncertain outcomes remain independently
  inspectable; refresh reconciles the live MediaLibrary listing without treating FileIndex or
  Result history as physical-file authority.
- Add MediaLibrary action controls to the existing Files page and reuse the established dialog
  interaction patterns. The normal page remains read-only until an explicit command is chosen;
  inputs stay available after correctable failures, pending controls prevent duplicate submission,
  Escape/Cancel do not imply rollback, and focus/usable narrow-screen behavior remain intact.
- Keep the selected MediaLibrary and exact library-relative path bound through command admission,
  evidence, execution and refresh. Same-ID ResourceLibrary requests, stale Active/configuration
  revisions, escaped/aliased paths, unavailable or disabled Storage and unsupported capabilities
  must fail closed with secret-free, action-oriented recovery.
- Preserve Task 38.1/38.2 behavior, the complete ResourceLibrary Files command journey and
  Organize routes. Do not modify the user's dirty `docs/pics/文件页.png`, the canonical
  `docs/pics/媒体库页.png`, `config/alist.json` or credentials.

## Acceptance Criteria

- [ ] An authorized operator can complete Create Folder, Create supported Text File, single-item
      Rename, supported text Open/Edit/Save and Delete from `/ui-v2/medialib/files`; the page shows
      the affected MediaLibrary-relative location, closes or reconciles only after a known result,
      and retains correctable input after a recoverable failure.
- [ ] MediaLibrary API and Web use the same application behavior and permissions for command
      admission, text access, delete impact and rename evidence. ResourceLibrary endpoints and
      behavior remain compatible, and equal IDs cannot exchange authority.
- [ ] Every mutation is executed only by `OrganizerExecutor`; analysis, browse, text read, impact,
      evidence, denied requests, invalid paths and failed admission perform zero Storage mutation
      and start no media pipeline work.
- [ ] The backend resolves the exact enabled MediaLibrary and its enabled Storage from the current
      Active snapshot, confines every source/target to the configured MediaLibrary root, rejects
      traversal, symlink/alias escapes, wrong entry types, stale version evidence, conflicts,
      unsupported capabilities and disabled/unavailable bindings without silently falling back.
- [ ] Delete is explicit and bounded; text Save is an explicit replacement intent; Rename is
      single-item and evidence-bound; supported text type/size and provider limits are enforced
      honestly in both API and Web. No arbitrary binary/media/image editing or silent overwrite is
      introduced.
- [ ] Durable command/task/result projections preserve independent success, failure, partial and
      uncertain per-item outcomes, known effects and safe next actions. Uncertain mutation is never
      replayed automatically, and a fresh live listing can reconcile a known successful result.
- [ ] Focused, affected regression, T4 quality gates and MediaLibrary desktop/narrow browser
      journeys pass with actual totals, skips and unavailable gates reported. The checkpoint is
      limited to this Task, contains no credentials or forbidden files, and does not weaken or
      delete existing tests.

## Required Tests

Run from the repository root unless a `web/` prefix is shown. Use local fakes and temporary
Storage only; never use production services, credentials or user media.

- `python3 scripts/check_governance.py`
- Add and run focused Python tests for MediaLibrary direct command resolution, exact Active/library
  and path authority, all command success/failure/conflict/capability cases, zero-mutation
  analysis, stale evidence, uncertain outcomes and ResourceLibrary compatibility.
- `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_operations.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_transfers.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'`
- `.venv/bin/python -m unittest discover -s tests`
- Add and run focused frontend model/API/dialog/page tests for MediaLibrary commands, malformed
  responses, permissions, retained input, explicit confirmation, no automatic replay and per-item
  result reconciliation.
- `npm --prefix web run test -- --run`
- `npm --prefix web run test:e2e -- tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts`
  including desktop and supported narrow viewport success, denied, conflict and recovery journeys.
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run format:check`
- `npm --prefix web run build`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- Confirm the FFmpeg/FFprobe exclusion with the repository-available grep command.
- `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py`
- Inspect `git diff --check`, the complete Task Base..Head manifest, private files and both
  reference images. Preserve the pre-existing dirty Files image.

## Non-goals

- MediaLibrary Copy/Move or cross-MediaLibrary transfer admission, cross-Storage
  Copy→verify→Delete-source semantics, durable transfer Worker reconstruction, Operations revisit
  or transfer-specific recovery. These require the next transfer/recovery Task.
- MediaLibrary Organize, Scan, Preview, recognition, metadata lookup, naming, classification,
  thumbnails, stream inspection, full-library statistics, Upload/Download or arbitrary binary,
  image or video editing.
- Batch Rename, unbounded recursion/global search, automatic directory-creation policy changes,
  silent overwrite/delete, implicit operation fallback or automatic replay of uncertain mutation.
- New Storage providers, broad configuration migration, identity-system changes, V1 cutover,
  shared shell redesign, changes to ResourceLibrary semantics, or changes to the A-owned Slice
  Contract/Roadmap.
- Controlled Slice screenshots, remaining RO-6/RO-7/RO-8 integration closure and Slice Final.

## Developer Completion Report

### Changed Files

Committed in `8cfddad289d2883a17f915e96162ae9e52724140` (Task Base `fabdb35`):

```text
mediaflow/domain/direct_files.py                     | 104+  13-  LibraryKind + kind-bound identity/tokens (new)
mediaflow/domain/task_persistence.py                 |  23+   0-  media_-prefixed durable command names (new)
mediaflow/application/direct_file_commands.py        | 224+ 111-  one command service, two immutable library kinds
mediaflow/application/file_catalog.py                |  12+   0-  media rows excluded from ResourceLibrary file detail
mediaflow/application/operations_lifecycle.py        |  11+   1-  task-item document: configured ID + explicit kind
mediaflow/application/processing_checkpoint.py       |  12+   2-  checkpoint document: same un-scoping, media-only key
mediaflow/interfaces/service_api.py                  | 239+ 103-  /api/v1/media-libraries/{id}/files/* + shared helpers
tests/test_direct_file_operations.py                 |  89+ 103-  service parameter rename (behavior unchanged)
tests/test_media_library_direct_commands.py          |1288+        focused MediaLibrary command proof (new, 21 tests)
web/src/entities/library/direct-files.ts             |  59+   9-  kind-safe strict models for both libraries
web/src/entities/library/direct-files.test.ts        |  25+   1-  identity projection + cross-kind rejection
web/src/features/library/MediaLibraryFilesPage.tsx   | 735+   4-  five command journeys on the media page (new surface)
web/src/features/library/MediaLibraryCommands.test.tsx | 1072+    page/dialog proof (new, 19 tests)
web/src/features/library/FileCommandDialogs.tsx      |  27+   5-  shared dialog focus fix + library-honest root label
web/src/features/library/media-library-query.ts      |  15+   0-  media text/impact/evidence query keys
web/src/shared/api/api-client.ts                     | 213+  62-  typed media command client (kind-guarded)
web/src/shared/api/media-library-commands-api.test.ts| 485+        client contract proof (new, 20 tests)
web/tests/fake-server.mjs                            | 624+   2-  session-mutating media command routes (test-only)
web/tests/e2e/medialib-commands.spec.ts              | 424+        browser command journeys (new, 12 tests)
```

The pre-existing dirty `docs/pics/文件页.png` is deliberately **not** in the checkpoint and is
preserved byte-identical (same hash as at Task Base) in the worktree. The canonical
`docs/pics/媒体库页.png` was not touched. `config/alist.json` remains absent and ignored; the commit
manifest contains no image, credential, private config, SQLite file or build artifact.

### Implemented

- **Kind-bound command authority (backend).** `DirectFileCommandService` is parameterized by an
  immutable `LibraryKind`; the API builds one ResourceLibrary and one MediaLibrary instance against
  the same pinned Active revision. A media command resolves only an enabled MediaLibrary with an
  enabled Storage from the exact Active snapshot, confines every source/target to the configured
  library root (traversal, absolute/escaped paths, symlink/alias escape, wrong entry type,
  unsupported capability, disabled/unavailable binding, conflict and stale version all fail closed
  with secret-free, action-oriented recovery), and executes only through `OrganizerExecutor`. Equal
  ResourceLibrary/MediaLibrary IDs cannot exchange authority: the kind enters every issued
  `entry_version_token`, every confirmed delete scope digest, and every evidence/confirmation check,
  so cross-kind evidence and cross-kind confirmation are refused (`files_direct_stale_source` /
  `files_direct_stale_confirmation`).
- **Honest durable attribution without migration.** A MediaLibrary command persists a `media:<id>`
  namespaced identity into the existing `task_items.resource_library_id` column and a `media_`
  command name (`media_files_direct_command` / `media_files_delete`), while every ResourceLibrary
  row and command name stays byte-identical; legacy bare rows read as resource. The operations and
  checkpoint projections un-scope that value back to the configured ID plus an explicit
  `library_kind`, so the persistence namespace never surfaces as part of a library ID, and
  `checkpoint_version` digests of pre-existing rows are unchanged (the media-only key is added only
  for media rows). Media rows are excluded from ResourceLibrary File/Media detail history, and media
  commands start no media-pipeline work (asserted against the task projections).
- **API.** New read routes `/api/v1/media-libraries/{id}/files/{text,delete-impact,rename-evidence}`
  (`READ`) and `/api/v1/media-libraries/{id}/files/commands` (`EXECUTE_MANUAL_ORGANIZE`) share one
  kind-parameterized transport helper set with the resource routes, so admission, limits, error
  envelopes, audit route patterns and response shape behave identically. Responses name the caller's
  own kind (`mediaLibraryId`, `libraryKind`, `taskCommand`); ResourceLibrary response bytes are
  unchanged (regression-tested), and every media surface fails closed with
  `configuration_unavailable` when no Active runtime exists.
- **Web.** `/ui-v2/medialib/files` now offers Create Folder, Create supported Text File, single-item
  Rename, bounded text Open/Edit/Save and Delete using the established dialog patterns. The page
  stays read-only until an explicit command; the selected MediaLibrary and exact library-relative
  path stay bound through admission, evidence, execution and refresh; pending dialogs prevent
  duplicate submission; correctable failures retain input; Escape/Cancel never imply rollback;
  dialogs close or reconcile only on a known result; the refreshed live listing (not the Result
  history) reconciles success, prunes deleted paths and remap-renames browse/tree state; per-item
  delete outcomes and uncertain outcomes stay independently visible and are never auto-replayed;
  the bounded selection cap (50) and text type/size limits are enforced honestly in both API and
  Web. The shared Delete dialog names the protected root as the library kind actually maintained.
- **Shared dialog focus fix.** The shared `ModalDialog` captured the invoking control with the
  autofocus already inside the dialog, so closing restored focus to a removed node; capture now
  happens at render time. This is a real defect in shared code surfaced by the media journeys; the
  Files page keeps its existing behavior and the full ResourceLibrary e2e suite still passes.
- **Preserved.** Task 38.1 browsing/route state and Task 38.2 configuration journeys, the complete
  ResourceLibrary Files command journey, and Organize routes.

### Tests and Results

All commands from the repository root unless a `web/` prefix is shown; temporary Local Storage and
local fakes only, no production service, credential or user media.

| Command | Result |
|---|---|
| `python3 scripts/check_governance.py` | PASS |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_direct_commands.py'` (new focus) | PASS — 21 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_operations.py'` | PASS — 55 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_transfers.py'` | PASS — 94 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'` | PASS — 13 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_browser.py'` | PASS — 5 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_activation.py'` | PASS — 19 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_resource_library_activation.py'` | PASS — 14 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_operations_workspace.py'` | PASS — 20 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_processing_checkpoint.py'` | PASS — 11 tests |
| `.venv/bin/python -m unittest discover -s tests` | PASS — 1766 tests, 7 skipped (pre-existing conditional skips) |
| `npm --prefix web run test -- --run` | PASS — 591 tests / 42 files (Task Base: 551 / 40; new: 19 page + 20 client + 1 model case) |
| `npm --prefix web run test:e2e -- tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts` | PASS — 24 tests (12 new command journeys, desktop + 760px narrow) |
| `npm --prefix web run test:e2e` (full browser suite) | PASS — 160 tests |
| `npm --prefix web run typecheck` | PASS |
| `npm --prefix web run lint` | PASS |
| `npm --prefix web run format:check` | PASS |
| `npm --prefix web run build` | PASS |
| `.venv/bin/ruff format --check .` | PASS — 313 files already formatted |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | PASS |
| `.venv/bin/python -m pip check` | PASS — no broken requirements |
| `.venv/bin/mediaflow --config config/strategy.example.json config validate` | PASS |
| `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` | PASS |
| FFmpeg/FFprobe exclusion (`rg -n -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml`) | PASS — no matches (`rg` unavailable; verified with the grep tool and `grep -rniE`) |
| `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py` | PASS — executed against the committed Head `8cfddad` |

`git diff --check` clean (working tree and staged content). No test was weakened or deleted;
`tests/test_direct_file_operations.py` only follows the command-service parameter rename.

### Decisions

- **One service, two kinds, no parallel implementation.** Parameterizing `DirectFileCommandService`
  with an immutable `LibraryKind` (and one binding slot per kind) keeps admission, evidence,
  confirmation, executor-only mutation and durable attribution provably identical for both
  journeys — satisfying "same application behavior and permissions" without copy-drift. The two
  instances can never resolve each other's libraries.
- **Kind inside every token, not beside it.** Adding `libraryKind` to the version-token payload and
  the delete scope digest is what makes equal-ID isolation real; the cost is that previously issued
  (short-lived, in-dialog) tokens no longer match after deployment, which forces exactly one
  evidence reload and mutates nothing.
- **`media:`-namespaced durable identity instead of a schema migration.** Reusing the TEXT
  `task_items.resource_library_id` column with an explicit prefix keeps every ResourceLibrary row,
  command name and `checkpoint_version` byte-stable, gives media rows their own authority namespace
  for free, and is un-scoped at every operator projection boundary. A dedicated column would need a
  broad migration this Task forbids; the asymmetry is documented in code and operator documents.
- **`media_files_delete` / `media_files_direct_command` mirror the resource command names** so Task
  listings, audit routes and the recovery UI classify media maintenance as its own family without
  inventing a second state machine.
- **MediaLibrary needs no FileIndex fan-out.** MediaLibrary content never enters FileIndex or
  `/api/v1/files*`, so the only cross-kind leak risk was source-path-keyed task history — closed by
  excluding media-kind rows from ResourceLibrary File/Media detail.
- **Shared-code touches were kept minimal and regression-proven**: the `ModalDialog` focus capture
  fix (a real defect) and a defaulted `rootLabel` prop (Files keeps its exact wording). Both are
  covered by the existing Files unit/e2e suites.

### Remaining In-Slice Work

- MediaLibrary Copy/Move transfer admission and any cross-Storage/Copy→verify→Delete semantics
  (explicitly deferred by this Task; the transfer service remains ResourceLibrary-only).
- Surfacing `library_kind` in the Web Operations/TaskItem views: the backend documents now carry it,
  the frontend normalizers are lenient and still render media rows by `storageId:sourcePath`; showing
  the kind as operator-visible attribution belongs with the Operations revisit Task.
- Recovery/Retry machinery intentionally does not execute media direct-command Tasks (they complete
  synchronously and are never replayed); a transfer/recovery Task should formalize that gate if it
  wants a dedicated state rather than the current refuse-and-explain behavior.
- Remaining RO-6/RO-7/RO-8 integration closure, controlled Slice screenshots and Slice Final are
  B/A-owned and untouched here.

### Risks / Deviations

- **Token payload change** (above): live in-flight dialogs reload evidence once; no durable state is
  affected and no mutation path changes.
- **Asymmetric persistence naming** (`media:<id>` inside the `resource_library_id` column) is the
  deliberate zero-migration compromise; any future consumer that joins task rows by that column
  without un-scoping would see media rows as an unknown library rather than as ResourceLibrary work
  (fail-closed, never cross-authority). Operator documents already un-scope it.
- **Fake-server RBAC gate added for media commands** (read-only principals are refused) mirrors real
  API behavior; test-only.
- **`tests/test_direct_file_operations.py` parameter rename** (`resource_library_id=` →
  `library_id=`) is mechanical; transfer-service call sites were left untouched because transfers
  remain resource-only by construction.
- **No pre-existing/unrelated failures.** Every gate above passes on the committed revision; nothing
  is reported as `FAIL / PRE-EXISTING / UNRELATED`; no required gate was unavailable (`rg`
  substitution noted, same evidence).
- **Inherited residual risk unchanged.** The narrow Local directory replacement/inode-reuse race
  documented in `SLICE.md` is untouched, and no new Storage-mutation, overwrite or deletion
  semantics were introduced beyond the bounded, executor-only commands this Task defines.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 8cfddad289d2883a17f915e96162ae9e52724140
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
