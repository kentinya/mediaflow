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
It must also correct the confirmed Task-Base Copy/Move directory regression described below because
that regression breaks this Task's explicit preservation acceptance and the same
ResourceLibrary-relative directory traversal boundary is required by Upload and Download.
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

### Confirmed Task-Base Regression: non-empty ResourceLibrary roots

Read-only diagnosis against the current Task Base and the running Active configuration confirmed
that Copy and Move reject every selected non-empty directory when the source ResourceLibrary has a
non-empty `storagePath`, regardless of whether the destination is on the same ResourceLibrary,
another ResourceLibrary on the same Storage, or another Storage. Single-file transfers remain
functional.

The failure occurs during zero-mutation `transfer-impact` manifest construction, before Task
admission or any Storage mutation. `_enumerate_directory` calls `Storage.list` with the full
Storage-relative path (`ResourceLibrary.root_path + current`) but compares each returned
Storage-relative `StorageEntry.path` directly with `current/child.name`, which is
ResourceLibrary-relative. The legitimate ResourceLibrary-root prefix therefore causes
`files_transfer_invalid_path`. The current bounded-directory tests set both ResourceLibrary
`storagePath` values to empty strings, so they do not cover this production configuration.

The correction must establish one explicit conversion boundary: validate each listed child as a
direct child in Storage-relative coordinates, strip exactly the configured ResourceLibrary root,
and store/recurse only with the resulting confined ResourceLibrary-relative path. It must not
merely remove the direct-child check, weaken confinement, leak Storage roots into manifests/results
or alter the existing zero-mutation admission guarantee.

## Implementation Scope

```text
Domain transfer/upload-download vocabulary and bounds
→ ResourceLibrary-relative directory traversal shared by Copy/Move/Upload/Download
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
- **Copy/Move directory regression**: normalize provider-returned Storage-relative directory
  entries to confined ResourceLibrary-relative paths before manifest validation, persistence or
  recursion. Preserve exact-root confinement, direct-child validation, symlink rejection, bounded
  depth/item/byte accounting, no-overwrite behavior and zero mutation during `transfer-impact`.
  The same rule must hold for Local, SMB, OpenList and S3/R2 adapter path conventions and for same-
  and cross-Storage transfers; no adapter-specific bypass is allowed.
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
- [ ] Copy and Move accept a bounded non-empty directory beneath a non-empty ResourceLibrary
      `storagePath`, for same-ResourceLibrary, different-ResourceLibrary/same-Storage and
      cross-Storage destinations. Manifests, results and UI evidence remain ResourceLibrary-relative;
      traversal, escaped/mis-parented provider entries and double-prefixed roots still fail before
      Task admission or mutation with stable actionable errors.
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
zero-mutation behavior, confinement and secret-free output. `tests.test_direct_file_transfers` must
add the missing non-empty ResourceLibrary-root directory matrix for Copy and Move across same
ResourceLibrary, different ResourceLibraries on one Storage and cross-Storage destinations, plus a
provider-double case that returns an escaped or non-direct child and remains fail-closed.

## Non-goals

- Resumable/chunked upload sessions across requests, browser drag-and-drop polish beyond the
  standard picker, download resume ranges, or transfer to arbitrary host paths.
- The Files-originated multi-item Organize continuation and terminal Organize→FileIndex
  reconciliation journey (RO-8 remainder) — the next Task.
- Media recognition/metadata/naming/classification changes, new Storage providers or capabilities,
  unbounded recursion/batches, arbitrary binary/media-content editing.
- Replace/overwrite upload conflict mode, cross-ResourceLibrary upload, or any weakening of the
  Task 37.3/37.4 safety contracts.
- Broad Copy/Move redesign beyond the confirmed ResourceLibrary-root directory path-coordinate
  regression and its required safety/regression coverage.
- Broad non-Files redesign, V1 cutover, P2/P3 cleanup or work outside Slice 37.

## Developer Completion Report

### Changed Files

Implementation (new):

- `mediaflow/application/direct_file_uploads.py` — bounded Upload service: manifest
  validation, confined scope pinning, durable `files_upload` Task, streaming
  per-item writes through `OrganizerExecutor`, per-item outcomes, safe-boundary
  pause/cancel/truncation.
- `mediaflow/application/direct_file_downloads.py` — confined zero-mutation
  Download service: bounded admission enumeration, single-file direct stream,
  on-the-fly bounded ZIP archive with an honest bounded manifest entry.
- `tests/test_direct_file_uploads.py`, `tests/test_direct_file_downloads.py` —
  focused upload/download suites (executor-only writes, conflict truth, limits
  before/during streaming, truncation, fault-injected partial/uncertain writes,
  capability denial, archive enumeration, zero-mutation, secret-free output).
- `web/src/features/library/FilesUploadDialog.tsx` — operator upload surface
  (files or one bounded directory tree, explicit conflict choice, bounded
  per-item results).

Implementation (modified):

- `mediaflow/application/direct_file_transfers.py` — Copy/Move directory
  regression fix: each listed provider child is converted by the single shared
  confined traversal rule before it enters the manifest/execution scope.
- `mediaflow/application/storage_browser.py` — shared confined
  directory-child conversion rule (`_confined_directory_child`).
- `mediaflow/application/organizer.py` — `execute_direct_write_stream`
  (the executor's streamed-write boundary for Upload; `overwrite=False`
  only; partial artifacts reported as unverified effects) and nullable
  `effect_certainty` defaulting in `_direct_result`.
- `mediaflow/domain/direct_files.py` — Upload/Download limit constants,
  conflict/status enums, manifest and result domain types, bounded
  `UploadResult.document()`.
- `mediaflow/domain/task_persistence.py` — `FILES_UPLOAD_TASK_COMMAND`.
- `mediaflow/interfaces/service_api.py` — authenticated
  `POST .../files/uploads` and `GET .../files/download` routes; bounded
  request framing reader (`_FilesUploadFraming`); shared streaming response
  helper; download selection query parsing.
- `web/src/entities/library/direct-files.ts` — upload result / download
  selection models + strict normalizers.
- `web/src/shared/api/api-client.ts` — `uploadFiles` (bounded streaming
  request body), `downloadFiles` (authenticated bounded read) and
  `saveDownloadedFile`.
- `web/src/features/library/StorageFilesPage.tsx` — Upload toolbar entry,
  per-row and selection-bounded Download actions, bounded error/recovery
  messaging; `StorageFilesPage.test.tsx` and `tests/setup.ts` extended.
- `tests/test_direct_file_transfers.py` — non-empty-ResourceLibrary-root
  Copy/Move matrix (same library, different library on one Storage,
  cross-Storage) plus fail-closed provider-double and symlink regressions.

### Implemented

- Fixed the confirmed Task-Base Copy/Move directory regression: a non-empty
  ResourceLibrary `storagePath` no longer makes directory enumeration compare
  provider storage-relative child paths against ResourceLibrary-relative
  targets; the single shared confined conversion rule validates the direct
  child in storage-relative coordinates and strips exactly one configured
  root, so escaped/mis-parented entries and double-prefixed roots fail
  closed before Task admission or mutation.
- Bounded Upload into the current directory from `/ui-v2/library/files`:
  one declared-length request body carries a confined JSON manifest ahead of
  the per-item byte payloads. Admission is zero-mutation (path safety,
  count/depth/per-file/aggregate byte limits, destination directory and type,
  capability, conflicts); only then is one durable `files_upload` Task
  admitted and each item's exact bytes streamed through a new
  `OrganizerExecutor.execute_direct_write_stream` boundary (no-overwrite
  only). Per-item outcomes are independent and durable; `no_overwrite`
  (default), `skip` and backend-named `keep_both` are explicit; uncertain or
  partially-written items are recorded and never auto-replayed; pause/cancel
  stop at safe item boundaries; a truncated request stream leaves remaining
  items honestly short of bytes.
- Bounded Download of one file, one bounded directory or a bounded
  multi-selection: single regular files stream directly with a truthful
  filename/content type/length; directories and multi-selections stream one
  on-the-fly ZIP archive (directory entries as zero-byte entries) with an
  appended bounded JSON manifest recording honest per-entry outcomes;
  admission enumerates within entry/depth/byte limits before any byte of
  the body is committed; there is no Task, no `OrganizerExecutor` call, no
  archive written back to Storage and no host-path/credential exposure.
- Wired both journeys through the authenticated API (RBAC: upload requires
  `EXECUTE_MANUAL_ORGANIZE`, download requires `READ`) and the Web UI:
  an Upload toolbar entry with a files/directory picker and explicit
  conflict choice, plus per-row and selection-bounded (≤50) Download
  actions with bounded secret-free error/recovery messaging and live-state
  refresh on success.

### Tests and Results

- New focused suites: `tests.test_direct_file_uploads` (16 tests) and
  `tests.test_direct_file_downloads` (9 tests) cover success, invalid
  input, permission/capability denial, confinement, conflicts, limits
  before and during streaming, truncated/interrupted transfers,
  partial/uncertain effects (fault-injecting Storage doubles), executor-only
  upload mutation, zero-mutation download and secret-free output — all with
  fakes, temporary roots and local processes only.
- `tests.test_direct_file_transfers` gained the required non-empty-root
  matrix: Copy and Move accept a bounded non-empty directory beneath a
  non-empty `storagePath` for same-ResourceLibrary,
  different-ResourceLibrary/same-Storage and cross-Storage destinations;
  manifests/results stay ResourceLibrary-relative; an escaped
  (non-direct-child) provider listing and a symlink child beneath a
  non-empty root both fail closed before any mutation.
- T4 gates at this checkpoint (truthful accounting):
  - `scripts/check_governance.py` — PASS.
  - `.venv/bin/ruff format --check .` / `.venv/bin/ruff check .` — PASS.
  - `.venv/bin/python -m unittest discover -s tests` — 1719 tests, 3
    failures, 7 skipped. The 3 failures
    (`test_manual_operations_contract::test_real_api_documents_carry_no_forbidden_evidence`,
    `test_manual_operations_contract::test_real_api_documents_match_the_frontend_fixture`,
    `test_configuration_status::test_hostile_configuration_content_is_never_exposed`)
    are pre-existing and environmental: they fail identically with all Task
    37.5 changes stashed (this host runs as user `root`, so the
    "no host path / no 'root' string" redaction assertion and the two
    fixture-bound contract documents are disturbed by the environment, not
    by this Task). No Task 37.5 test or module is among the failures.
  - Required focused suites all PASS:
    `test_direct_file_uploads` (16), `test_direct_file_downloads` (9),
    `test_direct_file_transfers` (90), `test_direct_file_operations` (55),
    `test_organizer` (23), `test_organizer_mutation_authority` (10),
    `test_organizer_rollback` (12), `test_local_storage` (25),
    `test_task_persistence` (13), `test_api_security` (13).
  - `python -m compileall -q mediaflow tests scripts` — PASS;
    `python -m pip check` — no broken requirements.
  - `ffprobe`/`ffmpeg` scan under `mediaflow` + `pyproject.toml`: clean.
  - `web` gates: `npm run format:check` PASS, `npm run typecheck` PASS,
    `npm run lint` PASS, `NODE_ENV=test npm run test -- --run` 458/458
    PASS (including the new bounded Upload/Download page tests),
    `npm run build` PASS.
  - Playwright `tests/e2e/library-files.spec.ts` — 28/28 PASS (the Files
    journey spec, including the preserved Copy/Move e2e truth).
    Full `npm run test:e2e` — 106 passed, 10 failed; all 10 failures are
    pre-existing in unrelated specs (`library-file-detail`,
    `manual-operations`) and reproduce identically with Task 37.5 changes
    stashed.
  - Docker security smoke test: UNAVAILABLE in this environment (Docker
    present but the release deployment fixture is incomplete — the runner
    fails with `bind source path does not exist: .../deployment.env`
    before any container check); recorded, not skipped silently.
  - Wheel build + `scripts/wheel_smoke_test.py` — PASS.

### Decisions

- Upload admission is a single request body ([4-byte BE manifest length],
  [manifest JSON], [per-item payloads]) so the interface layer validates
  the entire confined scope with zero mutation before streaming one byte;
  the framing reader is bounded by the declared `Content-Length`.
- Upload writes use a dedicated executor method
  (`execute_direct_write_stream`) rather than reusing `write` of the
  organize pipeline, keeping the OrganizerExecutor-only-mutation invariant
  while staying overwrite-free; checksums are recorded only for items
  within `MAX_UPLOAD_CHECKSUM_BYTES` so durable evidence stays bounded.
- Download never stages the archive: the ZIP is produced by a streaming
  sink whose chunks are drained into the WSGI response generator as they
  are made, and disappeared/changed entries are recorded in an appended
  bounded manifest entry instead of being fabricated.
- `UNCERTAIN` is an honest outcome (never auto-replayed); a clean
  pre-write conflict failure remains a retry-safe `FAILED`.

### Remaining In-Slice Work

- The Files-originated multi-item Organize continuation and terminal
  Organize→FileIndex reconciliation journey (RO-8 remainder) — the next
  Task; not implemented here by design.
- Browser drag-and-drop upload polish and resumable/chunked upload sessions
  across requests are explicitly non-goals for this Task.

### Risks / Deviations

- The Docker security smoke gate could not be executed in this environment:
  Docker is present, but the release deployment fixture is incomplete (the
  runner aborts with `bind source path does not exist:
  .../deployment.env` before any container check). It is recorded as
  UNAVAILABLE rather than green; no container assertions ran.
- Three Python full-suite tests and ten Playwright e2e tests are
  pre-existing failures unrelated to this Task (confirmed by re-running
  with all Task 37.5 changes stashed); they are environmental (this host
  runs as user `root`) and in specs outside the Files journey. No Task
  37.5 test or module is among them.
- `docs/pics/文件页.png` remains the pre-existing dirty file and was left
  untouched; `config/alist.json` is absent/untracked and no credentials
  entered the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: <set at commit>
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
