# Task 37.5 — Files Bounded Upload and Download

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.5
Parent Slice: 37
Status: PLANNED
Task Base: eeac5849b5489f91c26601b9878da5303879377d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete **RO-6 Complete common file management** and the **RO-7 Low-friction direct-operation
safety** / **RO-9 Actionable recovery** promises for the two remaining direct commands: an
authorized operator can upload one or more bounded browser-selected files or a bounded directory
tree into the current ResourceLibrary-relative directory, and can download one file, one bounded
directory, or a bounded multi-selection — entirely from `/ui-v2/library/files`, with no CLI, host
paths, raw credentials or media-organize ceremony.

Upload is a mutation and therefore crosses the same admission/confinement/`OrganizerExecutor`
boundary as every other direct command, with the Copy-conflict semantics (default no-overwrite;
explicit `跳过` / `保留两者`; Replace omitted). Download is a confined, zero-mutation, secret-free
read/stream: a single file streams directly; a directory or multi-selection streams as one bounded
archive generated on the fly without writing the archive back to managed Storage and without using
`OrganizerExecutor`.

This Task also advances **RO-11 Test reconciliation** and **RO-12 Security model continuity**.
It does not implement the remaining Files-originated multi-item Organize continuation or terminal
Organize→FileIndex reconciliation journey (RO-8 remainder) — that is the next Task.

## Why This Task Exists

Tasks 37.3–37.4 delivered Create Folder/Text File, Rename, Copy, Move, bounded text Edit and
Delete. The Files toolbar still cannot move operator-supplied content *into* the library (Upload)
or extract content *out* of it (Download), so RO-6's "Upload and Download for eligible
files/directories" is unmet and the common file-management journey is incomplete. Upload and
Download form one coherent unit because they share the browser file/ directory selection model,
the ResourceLibrary-relative destination/source resolution, the bounded per-item outcome model and
the progress/recovery surfaces — while having opposite authority semantics (mutation vs.
zero-mutation read), which this Task must keep sharply separated.

This is the largest independently reviewable next unit: the Organize/FileIndex remainder depends
on different authority (Preview/intent/execution) and stays separate.

Known constraints the design must respect:

- The interface layer is a bounded WSGI server (`mediaflow/interfaces/service_api.py`); bodies are
  read with an explicit `CONTENT_LENGTH` bound. Upload must stream `wsgi.input` in bounded chunks
  with declared request/file/count/depth limits and must not buffer a whole media file in memory.
- Download must stream from `Storage.read` through the WSGI response iterable; archives are built
  incrementally (streamed zip writer or equivalent), never staged on managed Storage or as an
  unbounded temp file.
- `Storage.read`/`Storage.write` stream interfaces already exist; every Storage capability is
  provider-advertised and must be checked, not assumed.

## Implementation Scope

```text
Domain transfer/upload-download vocabulary and bounds
→ application admission (upload) / read-authority (download)
→ OrganizerExecutor-only upload writes
→ authenticated API (bounded multipart/form and streamed responses)
→ Web Upload/Download surfaces with per-item progress/outcome/recovery
→ tests
```

- **Domain**: add bounded upload/download limits (e.g. max files per upload request, max directory
  depth, max per-file and aggregate bytes, max download archive entries/bytes) next to the existing
  `MAX_TRANSFER_*` vocabulary; add upload-conflict and per-item outcome types. Limits must be
  explicit constants, enforced before and during streaming, with stable actionable error
  categories.
- **Upload admission**: browser submits only ResourceLibrary identity, the normalized relative
  destination directory, the relative path of every supplied item, an explicit conflict choice and
  the same pinned-Active evidence discipline as Copy/Move. Backend validates every supplied
  relative path (no absolute paths, separators in basenames where illegal, dot segments, path
  escape, ResourceLibrary-root overwrite), rejects symlink/unsupported entries and over-limit
  requests before the first byte is written.
- **Upload execution**: every file write and every directory creation crosses
  `OrganizerExecutor` with explicit mutation authority; conflicts default to no-overwrite (`跳过`
  skips, `保留两者/重命名` generates a backend-determined unique name, Replace omitted). Each item
  outcome is independent: one failed file never hides or blocks its siblings, successful siblings
  are never replayed, and an uncertain write is recorded truthfully and never automatically
  retried. Incomplete staging is removed only when safely provable; otherwise it is surfaced as a
  recoverable partial artifact. Multi-file and directory-tree uploads run through the existing
  Task system with bounded progress; a single small file may complete inline only through the same
  application/audit/executor boundaries.
- **Download admission and streaming**: resolve the selection through the current pinned Active
  ResourceLibrary/Storage; confine to relative paths; enumerate directories within the explicit
  item/depth/byte limits before streaming. A single file streams directly with a truthful
  filename/content type. A directory or multi-selection streams one archive whose manifest is
  bounded and enumerated first; entries that vanish or change mid-stream produce a truthful
  per-item outcome note inside the response trail (e.g. archive manifest entry or terminal error),
  never fabricated content. Download performs no Storage mutation, creates no mutation Task, does
  not invoke `OrganizerExecutor`, and never exposes Storage credentials, host paths or provider
  internals in headers, archive names or error bodies.
- **Interruption and recovery**: interrupted downloads are safe to restart as reads. Upload retry
  is per failed/known-safe item only; an uncertain destination write is never automatically
  repeated. Failure surfaces keep the Files context, state what exists at the destination, state
  whether retry is safe and offer a concrete next action.
- **Audit/results**: persist bounded secret-free evidence — actor, operation, logical
  ResourceLibrary-relative paths, item counts/sizes, conflict choices, statuses and stable
  failure/recovery categories. No host roots, credentials, raw provider responses or file content.
- **API**: add authenticated routes following current conventions (e.g. bounded multipart or
  declared-length upload submission plus per-item result document; `GET` download route with
  bounded selection encoding). Web and API must use the same application service, RBAC, snapshot,
  confinement and limits. Stable errors distinguish invalid selection/destination, capability
  denial, conflict, limit overflow, partial completion and uncertain effect.
- **Web**: add Upload (files and directory) and Download to the applicable toolbar, row and
  bounded-selection surfaces. Upload uses standard browser file/directory pickers; shows per-item
  progress, conflict choices and durable outcomes; preserves the current directory and unaffected
  selection on recoverable failure. Download triggers the streamed response without leaving Files
  and explains refused/empty selections. Keyboard, touch, Escape, focus restoration and
  duplicate-submit prevention remain supported at `1536 x 1024` and supported responsive widths.
- **Success refresh**: after known upload success, Files refreshes the live listing and
  clears/remaps only selection whose physical truth changed; download leaves all state untouched.
- **Preserve** Task 37.1–37.4 behavior (shell, browse/search/sort/paging, card strip, drawer,
  Create/Rename/Edit/Delete, Copy/Move, scrollable viewport, portal menus, organize Preview entry,
  non-Files routes, V1 `/ui`) and the pre-existing dirty `docs/pics/文件页.png`.

## Acceptance Criteria

- [ ] An authorized operator can upload one file, several files or one bounded directory tree into
      the current directory entirely from `/ui-v2/library/files`, and sees truthful per-item
      outcomes without CLI, host paths, credentials or organize ceremony.
- [ ] Every supplied relative path is backend-validated; absolute paths, traversal, escape beyond
      the selected ResourceLibrary root, ResourceLibrary-root overwrite, unsupported entry types
      and over-limit requests (count/depth/per-file/aggregate bytes) fail closed with an actionable
      reason before any write.
- [ ] Every upload write and directory creation crosses `OrganizerExecutor` after RBAC,
      pinned-Active, confinement, capability and conflict checks. Application/API/Web code performs
      no direct Storage mutation.
- [ ] Upload destination conflicts default to no-overwrite; `跳过` and backend-named `保留两者` are
      explicit and recorded per item; no path is silently overwritten. One failed item never hides,
      blocks or replays a sibling; uncertain writes are recorded and never automatically retried.
- [ ] Multi-file/directory-tree uploads use durable Tasks with bounded progress and independent
      per-item outcomes; pause/cancel take effect only at safe item boundaries and never convert
      an unknown effect into a retryable failure.
- [ ] Download of one file streams it directly; download of one bounded directory or a bounded
      multi-selection streams one archive built on the fly within explicit entry/depth/byte limits
      and is never written back to managed Storage.
- [ ] Download is a confined zero-mutation read: it creates no mutation Task, invokes no
      `OrganizerExecutor` method and no media pipeline stage, and exposes no host paths, Storage
      credentials or provider internals. Read-only Files interactions remain zero-side-effect.
- [ ] Over-limit or escaped download selections fail before streaming with an actionable reason;
      mid-stream source changes are reported truthfully rather than fabricated.
- [ ] API and Web share one application behavior and permission model; errors are bounded,
      secret-free and distinguish invalid selection, capability denial, conflict, limit overflow,
      partial completion and uncertain effect. Audit evidence is bounded and secret-free.
- [ ] Success refreshes authoritative live state and prunes only provably stale selection; failure
      or partial states keep the Files context, state what exists and give one safe next action.
      Upload retry is per known-safe failed item.
- [ ] Upload/Download controls and progress/result states are keyboard- and touch-operable,
      prevent duplicate submission and remain usable at `1536 x 1024` and responsive widths.
- [ ] Existing Create/Rename/Edit/Delete/Copy/Move, ResourceLibrary lifecycle, Files
      browse/selection, organize Preview, non-Files V2 routes and V1 `/ui` remain functional; no
      current safety assertion is removed, weakened or skipped.
- [ ] Focused tests use fakes/mocks/temporary roots only and cover success, invalid input,
      permission/capability denial, confinement, conflicts, limits (before and during streaming),
      truncated/interrupted transfer, partial/uncertain effects, pause/cancel, redaction,
      executor-only upload mutation and zero-mutation download. The T4 gates pass with truthful
      accounting of pre-existing/unrelated failures or unavailable external gates.
- [ ] The checkpoint contains only Task 37.5 implementation, tests and completion report. It
      excludes `config/alist.json`, credentials, the dirty reference image, ignored test artifacts
      and unrelated changes.

## Required Tests

- `python3 scripts/check_governance.py`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m unittest tests.test_direct_file_uploads tests.test_direct_file_downloads`
  (new modules, or the chosen equivalent names recorded in the completion report)
- `.venv/bin/python -m unittest tests.test_direct_file_transfers tests.test_direct_file_operations`
- `.venv/bin/python -m unittest tests.test_source_directory_cleanup tests.test_manual_organize_execution tests.test_configuration_organize`
- `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_organizer_rollback`
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage tests.test_openlist_storage tests.test_s3_storage`
- `.venv/bin/python -m unittest tests.test_runtime_files_browser tests.test_api_security tests.test_task_persistence tests.test_task_pause_resume tests.test_task_retry`
- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `python3 scripts/docker_release_security_smoke_test.py` (if the environment permits Docker
  bind mounts; otherwise record UNAVAILABLE with the reproduced error)
- `test -z "$(grep -rn -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml || true)"`
- `cd web && npm run format:check`
- `cd web && npm run typecheck`
- `cd web && npm run lint`
- `cd web && NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx`
- `cd web && npx playwright test tests/e2e/library-files.spec.ts --project=chromium`
- `cd web && NODE_ENV=test npm run test -- --run`
- `cd web && npm run build`
- `cd web && npm run test:e2e`
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist`
- `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl`
- `git diff --check`
- Inspect `git status --short`, the exact Task Base..Head diff and staged manifest; confirm
  `config/alist.json`, credentials, the dirty `docs/pics/文件页.png`, ignored local test artifacts
  and unrelated files are absent.

All tests use mocks, fakes, temporary roots and local test servers only. No production
SMB/OpenList/S3/TMDB service, credential or real media directory is permitted. Focused upload tests
must use fault-injecting Storage doubles and request streams to prove executor-only writes,
conflict truth, per-item independence, limit enforcement before/during streaming and no automatic
replay of uncertain writes. Download tests must prove bounded enumeration before streaming,
zero-mutation behavior, confinement and secret-free output.

## Non-goals

- Resumable/chunked upload sessions across requests, browser drag-and-drop polish beyond the
  standard picker, download resume ranges, or transfer to arbitrary host paths.
- The Files-originated multi-item Organize continuation and terminal Organize→FileIndex
  reconciliation journey (RO-8 remainder) — the next Task.
- Media recognition/metadata/naming/classification changes, new Storage providers or capabilities,
  unbounded recursion/batches, arbitrary binary/media-content editing.
- Replace/overwrite upload conflict mode, cross-ResourceLibrary upload, or any weakening of the
  Task 37.3/37.4 safety contracts.
- Broad non-Files redesign, V1 cutover, P2/P3 cleanup or work outside Slice 37.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: PLANNED — awaiting Developer implementation
Head SHA: NOT SET
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
