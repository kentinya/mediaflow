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

## Developer Completion Report (Correction Round 1)

### Changed Files

Implementation (modified):

- `mediaflow/interfaces/service_api.py` — the Upload transport is now the
  browser-native journey: bounded JSON admission (`POST .../files/uploads`,
  202 + durable Task identity, zero payload bytes), one raw-bytes payload
  request per item (`POST .../files/uploads/{taskId}/items/{index}`), a
  finish call (`POST .../files/uploads/{taskId}/finish`) and the durable
  projection (`GET .../files/uploads/{taskId}`). The custom binary framing
  and the request-scoped payload pump are removed.
- `mediaflow/application/direct_file_uploads.py` — per-item execution
  boundary (`execute_item`), durable finalization (`finish_upload`),
  manifest-order/duplicate payload refusal, `upload_projection` rebuilt from
  persisted Task/items/Results, admission persists every item PENDING so
  progress is pollable from the first read, truthful pause/cancel at item
  boundaries and honest refused outcomes for undelivered items.
- `mediaflow/application/direct_file_downloads.py` — the archive is
  produced by one bounded producer thread draining into a strictly bounded
  chunk queue (peak memory independent of file/archive size); every file
  entry is re-validated at the read boundary against the pinned
  provider-neutral evidence (type, size, mtime, fingerprint); the same
  evidence re-validation guards the single-file stream and refuses a
  same-size replacement, a shrink or a vanished source before any byte is
  published.
- `mediaflow/domain/direct_files.py` — `DownloadArchiveEntry` pins the
  admission-time `modified_at`/`fingerprint` evidence.
- `web/src/shared/api/api-client.ts` — `uploadFiles` runs the full
  production journey with browser-computed lengths only (JSON admission,
  per-item raw byte bodies, finish), exposes the admitted Task identity via
  `onAdmitted`; `fetchUploadProjection` polls the durable projection; no
  ReadableStream request body, no script-set Content-Length, no `duplex`.
- `web/src/features/library/FilesUploadDialog.tsx` — live per-item progress
  and the backend-advertised pause/cancel controls rendered from the durable
  projection; the terminal projection's items are the authoritative result
  view.
- `web/src/features/library/StorageFilesPage.tsx` — upload mutation admits
  the Task and starts the projection poll (700 ms, stops at terminal);
  pause/cancel go through the existing operator lifecycle route with the
  projection's version for the compare-and-set.
- `web/src/entities/library/direct-files.ts` —
  `FilesUploadProjection` model + strict normalizer.
- `tests/test_direct_file_uploads.py` — per-item journey coverage: the
  framed end-to-end API tests (B's exact `existing.mkv=blocked` →
  `ok.mkv=ok` reproduction, out-of-order/duplicate refusal, admission
  limits, projection route RBAC, operator lifecycle pause/cancel), durable
  projection truth, cancel/pause at safe item boundaries, per-item
  truncation.
- `tests/test_direct_file_downloads.py` — B3: archive streaming proven to
  yield response bytes while the source read is still blocked (bounded
  memory independent of file size); B4: same-size replacement (archive +
  single-file) and vanish are refused/reported, never fabricated.
- `web/tests/fake-server.mjs` — the fake API serves the real upload journey
  (admission, per-item payload POSTs, projection, finish, pause/cancel).
- `web/tests/e2e/library-files.spec.ts` — new real-browser e2e: upload
  streams a picked file through admission → per-item payload → projection
  poll → finish with zero 4xx/5xx, silent error surface and no Task-ID
  ceremony.

### Implemented

- B1 (Upload transport): the browser posts one bounded JSON manifest with
  the browser-computed Content-Length, then streams each item's exact bytes
  as its own request body. No script-set `Content-Length`, no
  `duplex`, no ReadableStream request body — verified in real Chromium by
  the new e2e.
- B2 (framing/poisoning): with one request per item, one item's payload can
  never be consumed as (or by) a sibling's: the admission refuses
  out-of-order and duplicate payload requests (`item_out_of_order`,
  `item_already_delivered`) before any read, and B's exact two-item
  reproduction passes through the real API path with the sibling's exact
  bytes intact.
- B3 (bounded archive memory): the ZIP is produced by a bounded producer
  thread whose output queue holds at most 32 bounded chunks while the WSGI
  generator drains; the test proves the first response chunk is produced
  while the source read is still blocked, so memory is bounded
  independently of file size.
- B4 (source identity): every file entry (single-file and archive) is
  re-validated at the read boundary against the pinned admission evidence
  (entry type, size, mtime, provider fingerprint); same-size replacement,
  shrink and vanish are refused or recorded honestly instead of being
  streamed as the admitted content.
- B5 (durable progress + pause/cancel): admission creates the Task with
  every item PENDING and returns its identity immediately, so the projection
  (per-item outcomes, counts, terminal state, advertised actions) is
  pollable from the first read; the Web renders that projection live and
  offers pause/cancel through the existing cooperative lifecycle route
  (compare-and-set on the projection's version); a pause acknowledges at the
  next item boundary and leaves the Task PAUSED (resume honestly
  unavailable — the browser bytes are not durable), cancel converges the
  Task to CANCELLED with zero further mutation; finish records every
  undelivered item's truthful refused outcome and publishes the honest
  terminal aggregate.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_direct_file_uploads` — 27 tests
  PASS (includes the new per-item framed API journeys, ordering refusals,
  projection lifecycle and operator pause/cancel routes).
- `.venv/bin/python -m unittest tests.test_direct_file_downloads` — 13
  tests PASS (includes bounded-stream and source-change coverage).
- `.venv/bin/python -m unittest tests.test_direct_file_transfers` — 90
  tests PASS (Copy/Move regression matrix unchanged and green).
- `.venv/bin/python -m unittest tests.test_direct_file_operations
  tests.test_source_directory_cleanup tests.test_manual_organize_execution
  tests.test_configuration_organize` — 112 PASS; organizer suites (45) PASS;
  storage suites (94) PASS; runtime/API/task suites (48) PASS.
- `.venv/bin/python -m unittest discover -s tests` — 1734 tests, 3
  failures, 7 skipped; the 3 failures
  (`test_manual_operations_contract` × 2,
  `test_configuration_status::test_hostile_configuration_content_is_never_exposed`)
  reproduce identically with all working-tree changes stashed (verified in
  this round) and are the same pre-existing environmental failures recorded
  in the original checkpoint (this host runs as `root`).
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` / `.venv/bin/ruff check .` — PASS.
- `python -m compileall -q mediaflow tests scripts` — PASS;
  `python -m pip check` — clean; ffprobe/ffmpeg scan — clean.
- `web`: `format:check` PASS, `typecheck` PASS, `lint` PASS,
  `NODE_ENV=test npm run test -- --run` 458/458 PASS, `npm run build` PASS.
- Playwright `tests/e2e/library-files.spec.ts --project=chromium` — 29/29
  PASS (28 preserved + the new real-browser upload journey).
- Wheel build + `scripts/wheel_smoke_test.py` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE,
  unchanged from the original checkpoint: the release deployment fixture is
  incomplete and the runner aborts on a missing bind source
  (`mediaflow.json` / `deployment.env`) before any container check; the
  identical failure reproduces with all changes stashed.

### Decisions

- One request per item replaces the single framed body. This makes payload
  misalignment structurally impossible (B2's root cause), gives the browser
  a transport it supports natively (B1's root cause), and turns each item
  boundary into a real safe pause/cancel boundary (B5).
- The durable projection is rebuilt from persisted Task/items/Results only,
  so polling is correct from admission, during streaming and after a process
  restart; resume is advertised as unavailable because the payload bytes
  were never durable (an honest refusal, not a fake continuation).
- Download memory bounding uses a bounded producer queue rather than
  buffering per file; the re-validation evidence is provider-neutral (size,
  mtime, fingerprint when the provider advertises one) and confined — no
  host paths or provider internals are exposed.
- UNCERTAIN remains an honest outcome; a clean pre-write conflict failure
  stays a retry-safe FAILED.

### Remaining In-Slice Work

- The Files-originated multi-item Organize continuation and terminal
  Organize→FileIndex reconciliation journey (RO-8 remainder) — the next
  Task; not implemented here by design.
- Browser drag-and-drop upload polish and resumable/chunked upload sessions
  across requests are explicitly non-goals for this Task.

### Risks / Deviations

- The Docker security smoke gate remains UNAVAILABLE in this environment
  (pre-existing, reproduced with the changes stashed; fixture bind sources
  are missing before any container check).
- The three pre-existing full-suite failures are unrelated and reproduce on
  the base state (verified again in this round); no Task 37.5 test or module
  is among them.
- Providers that publish no fingerprint (SMB/OpenList/S3 regular entries)
  rely on size + mtime as the same-size replacement evidence; a replacement
  that preserves both is not detectable with provider-neutral metadata
  alone. This is the strongest pin available without reading content or
  buffering, and is recorded here for B's judgement.
- `docs/pics/文件页.png` remains the pre-existing dirty file, untouched;
  `config/alist.json` is absent and no credentials entered the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 699a5516bec32f9782fbc5ccb38da7189c034e5e
```

## Developer Completion Report (Correction Round 2)

### Changed Files

Implementation (modified):

- `mediaflow/domain/direct_files.py` — new `UploadSessionPhase` state
  machine (`RUNNING` / `PAUSED` / `CANCELLED` / `FINISHED`).
- `mediaflow/application/direct_file_uploads.py` — the request-scoped
  `_admitted` dict is replaced by a bounded, task-keyed Upload Session
  registry above the replaceable runtime binding (`UploadSession`,
  `_register_upload_session`, `drop_upload_session`,
  `upload_session_item_size`, `resume_upload_session`, `MAX_UPLOAD_SESSIONS`).
  Each admitted session owns the exact validated plan and the exact pinned
  `direct_files`/executor binding from admission through terminal cleanup.
  Pause is now a truthful session phase: the boundary response is
  `status=PAUSED` with `paused: true` and `nextIndex` (never an item
  failure); finish while paused is refused (`finish_unavailable`) unless the
  durable Task is already CANCELLED; a genuinely lost in-process session
  fails with `files_upload_session_interrupted` (explicit interrupted/
  resubmit recovery) instead of `not_found`. `_unique_destination_name`
  now only accepts a genuinely absent generated name (B2's repeated-suffix
  root cause); directory-merge behavior is preserved at its own boundary.
  The projection advertises `resume` only while the live session is paused,
  and PAUSED rows no longer count as processed or render fabricated
  error categories.
- `mediaflow/interfaces/service_api.py` — `_files_upload_item` enforces that
  the request's `Content-Length` is present, numeric, non-negative and
  exactly equal to the admitted item size before any read or mutation (B4);
  new authenticated route
  `POST .../files/uploads/{taskId}/resume` (RBAC `EXECUTE_MANUAL_ORGANIZE`)
  delegating to `resume_upload_session` (B1).
- `mediaflow/application/direct_file_downloads.py` — the archive producer
  now speaks an explicit queue protocol (`data` / `_ArchiveEntryFailure` /
  `_ArchiveTerminal` / done) and never swallows producer exceptions: a
  recoverable per-entry read failure before any published byte ends the
  entry as an honest failed manifest outcome; a provider failure after the
  entry started breaks ZIP integrity, so the response aborts as a terminal
  `transfer_interrupted` (503) error instead of emitting a success-looking
  truncated archive (B5).
- `web/src/shared/api/api-client.ts` — `uploadFiles` stops before the next
  Blob POST when the boundary response says `paused` (surfacing
  `paused: true`, never calling finish), accepts a `resume` continuation
  ({taskId, startIndex}) that streams the remaining items of the same
  selection without a new admission, and `resumeUpload` calls the new
  backend resume route and returns the advertised `nextIndex` (B1).
- `web/src/features/library/StorageFilesPage.tsx` — the upload selection and
  conflict choice are captured in refs so the backend-advertised resume
  action continues the exact still-live selection from `nextIndex`; a lost
  selection explains the resubmit recovery instead of stranding the Task.
- `web/src/features/library/FilesUploadDialog.tsx` — renders the paused
  state (`上传已暂停…`) and the backend-advertised `继续上传` control from
  the durable projection's action list.

Tests (modified):

- `tests/test_direct_file_uploads.py` — rewritten pause truth
  (`PAUSED` boundary response, no item failure, finish refused while paused,
  durable rows stay `paused`), new full pause→resume→finish journey through
  the production routes (operator pause route → item boundary → projection →
  resume route → continuation → finish), pause-after-delivered resumes at
  `nextIndex`, paused-then-cancel without item failures, lost-session
  interrupted recovery, B2 repeated-suffix keep-both for files and
  directory nodes (plus the directory-merge boundary), and B3
  activation-between-admission/items/finish with a valid successor revision
  (the admitted upload keeps its pinned revision-A binding; a new upload
  uses the new Active).
- `tests/test_direct_file_downloads.py` — B5 mid-entry provider failure
  (fault-injecting Storage returns bytes then disconnects after response
  bytes began): the response aborts truthfully as `transfer_interrupted`
  (503) with zero mutation and no fabricated archive.
- `web/src/features/library/StorageFilesPage.test.tsx` — two new Web
  journeys: pause stops before the next Blob POST and the resume control
  continues the live selection to the honest terminal; paused-then-cancel
  converges without finish or item failures.
- `web/tests/fake-server.mjs` — the fake API now models the session truth:
  paused sessions refuse streaming until resumed, the deterministic
  `Movies/e2e-pause` demo directory pauses after the first delivered item,
  the new resume route, finish-while-paused refusal (409
  `finish_unavailable`), cancelled finish truth and the paused projection's
  advertised resume action.
- `web/tests/e2e/library-files.spec.ts` — new real-browser e2e driving the
  complete pause → resume → finish journey (no finish while paused, zero
  4xx/5xx, honest terminal).

### Implemented

- B1 (pause truth + resume): one explicit Upload Session state machine
  above the durable Task. Pause is acknowledged only at item boundaries
  between mutations, is never recorded as an item failure, and keeps
  undelivered items pending and resumable. The browser stops before the
  next Blob POST; the existing Task resume authority continues the paused
  upload with the still-live browser selection (`nextIndex`), then finish
  publishes the honest terminal aggregate. Cross-process, partial-item and
  browser-reload resume remain out of scope: those fail with the explicit
  interrupted/resubmit recovery instead of a fabricated continuation.
- B2 (keep-both collision): a generated keep-both destination is accepted
  only when genuinely absent — `existing.mkv` + `existing (1).mkv` now
  produce `existing (2).mkv` (and the file-occupies-directory-slot variant
  produces `Show (2)/note.txt`); existing directory merge at its separate
  boundary is preserved and pinned by its own test.
- B3 (pinned binding): the session registry above the replaceable runtime
  binding keeps the exact validated plan and pinned revision from admission
  through terminal cleanup, so a valid configuration activation between
  admission, item streaming and finish affects new uploads only; the
  registry is bounded (`MAX_UPLOAD_SESSIONS`) and evicts terminal sessions
  first, so eviction surfaces the interrupted/resubmit recovery.
- B4 (length contract): the per-item route fails closed on missing,
  invalid, negative, shorter or longer `Content-Length` before any read or
  mutation, with the exact-length case verified against the admitted item
  size through the WSGI route.
- B5 (producer protocol): the archive producer never swallows exceptions;
  entry-level read failures are classified at the read boundary, and a
  failure that breaks ZIP integrity aborts the response as a terminal
  transfer failure with bounded, secret-free recovery evidence instead of
  fabricating a success-looking archive.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_direct_file_uploads` — 39 tests
  PASS (pause truth, resume journey, pinned-binding activation, keep-both
  collisions, interrupted recovery, framed API journeys).
- `.venv/bin/python -m unittest tests.test_direct_file_downloads` — 14
  tests PASS (including the new mid-entry provider-failure abort).
- `.venv/bin/python -m unittest tests.test_direct_file_transfers
  tests.test_direct_file_operations` — PASS (197 combined with the two
  suites above; Copy/Move regression matrix unchanged and green).
- `.venv/bin/python -m unittest tests.test_source_directory_cleanup
  tests.test_manual_organize_execution tests.test_configuration_organize` —
  57 PASS; `tests.test_organizer tests.test_organizer_mutation_authority
  tests.test_organizer_rollback` — 45 PASS; storage suites
  (`test_local_storage test_smb_storage test_openlist_storage
  test_s3_storage`) — 94 PASS; `tests.test_runtime_files_browser
  tests.test_api_security tests.test_task_persistence
  tests.test_task_pause_resume tests.test_task_retry` — 48 PASS.
- `.venv/bin/python -m unittest discover -s tests` — 1747 tests, 3
  failures, 7 skipped; the 3 failures
  (`test_manual_operations_contract` × 2,
  `test_configuration_status::test_hostile_configuration_content_is_never_exposed`)
  reproduce identically on a clean checkout of HEAD with all working-tree
  changes excluded (verified this round via `git archive` into a separate
  directory) and remain the pre-existing environmental failures recorded in
  earlier checkpoints (this host runs as `root`).
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` / `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS;
  `.venv/bin/python -m pip check` — clean; ffprobe/ffmpeg scan — clean.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` —
  PASS; `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl`
  — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE,
  unchanged from previous rounds: the release fixture aborts before any
  container check because the bind source `deployment.env` is not created
  (`bind source path does not exist: .../deployment.env`).
- `web`: `format:check` PASS, `typecheck` PASS, `lint` PASS,
  `NODE_ENV=test npm run test -- --run` 460/460 PASS, `npm run build` PASS.
- Playwright `tests/e2e/library-files.spec.ts --project=chromium` — 30/30
  PASS (29 preserved + the new real-browser pause→resume journey).
- `git diff --check` — clean; `config/alist.json`, credentials, the dirty
  `docs/pics/文件页.png`, `web/test-results/` and `dist/` artifacts are
  absent from the checkpoint.

### Decisions

- The Upload Session is an in-process authority keyed by the durable Task
  identity, registered at admission and dropped only at terminal cleanup.
  It owns the already-validated plan and the pinned binding, which keeps
  the pinned-Active guarantee without a schema migration or a resumable/
  chunk protocol (both non-goals). The durable Task/items/Results remain
  the only persisted authority, so every projection is still rebuilt from
  them.
- Pause is modeled as a first-class phase whose boundary response is
  `status=PAUSED` (HTTP 200, `paused: true`, `nextIndex`), never an item
  failure; resume goes through the Task resume action over the live
  session and re-streams from the advertised index, so the browser bytes
  already delivered are never replayed.
- Finish-while-paused is refused (409 `finish_unavailable`) unless the
  durable Task already converged to CANCELLED, in which case finish
  records the honest cancelled aggregate — never a fabricated terminal
  state over an operator pause.
- Keep-both uniqueness is one rule everywhere: a generated destination is
  valid only when absent. Directory-merge stays a separate, deliberate
  boundary (an existing directory slot is merged into) and is pinned by
  its own regression test.
- Download archive integrity: a per-entry read failure before the entry's
  first published byte ends as a failed manifest entry (the ZIP stays
  valid); a failure after bytes were published cannot guarantee ZIP
  integrity, so the response aborts mid-stream as `transfer_interrupted`
  (503) — the operator never receives a truncated success-looking archive.

### Remaining In-Slice Work

- The Files-originated multi-item Organize continuation and terminal
  Organize→FileIndex reconciliation journey (RO-8 remainder) — the next
  Task; not implemented here by design.
- Resumable/chunked upload sessions across requests and browser
  drag-and-drop polish remain explicit non-goals of this Task.

### Risks / Deviations

- The Docker security smoke gate remains UNAVAILABLE in this environment
  (pre-existing, reproduced again this round; the fixture aborts on a
  missing bind source before any container check).
- The three pre-existing full-suite failures are unrelated and reproduce
  on the clean HEAD state (verified via a `git archive` checkout this
  round); no Task 37.5 test or module is among them.
- Resume remains in-process by design: a genuinely lost session (process
  restart, eviction under `MAX_UPLOAD_SESSIONS`, browser reload) refuses
  with `files_upload_session_interrupted` / `resume_unavailable` and the
  operator resubmits; already-recorded item outcomes stay durable in both
  cases. Cross-process resume would require durable browser bytes and is a
  Task non-goal.
- `docs/pics/文件页.png` remains the pre-existing dirty file, untouched;
  `config/alist.json` is absent and no credentials entered the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: <filled at commit>
```

## B Review Result

```text
Reviewed: eeac5849b5489f91c26601b9878da5303879377d..699a5516bec32f9782fbc5ccb38da7189c034e5e
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Upload pause is not a truthful, recoverable Task state on the production Web path.** After
  a pause is acknowledged at an item boundary, `execute_item` returns HTTP 200 with
  `upload_paused`, so
  `uploadFiles` continues to the next item; that request is then rejected because the Task is no
  longer running and the Web calls `finish`. `finish_upload` does not preserve the already-PAUSED
  Task status and converts the Task to `FAILED`, records every undelivered item as
  `upload_stream_truncated`, and the pre-finish projection counts PAUSED rows as processed while
  rendering them `PENDING`. A two-item Local upload reproduced `PAUSED` becoming `FAILED` with both
  items failed after `finish`. This violates Slice RO-6/RO-9, the required Files transfer-progress
  surface and this Task's durable-progress/safe-boundary Acceptance Criterion. Use one explicit
  Upload Session state machine (`RUNNING` / `PAUSED` / `CANCELLED` / `FINISHED`): acknowledge pause
  only between item mutations, make the browser stop before the next Blob POST, allow the existing
  Task resume action to continue with that still-live browser selection, and never treat pause as an
  item failure or call `finish` while paused. Cross-process, partial-item and browser-reload resume
  remain out of scope; those cases must expose an interrupted/resubmit recovery instead. Cover the
  complete Web/API pause-to-resume/cancel path rather than only the intermediate projection.
- **P1 — `保留两者` fails when the first generated suffix is already occupied by the same entry
  type.**
  `_unique_destination_name` treats an existing file as available when choosing a file name (and an
  existing directory as available when choosing a directory name). With `existing.mkv` and
  `existing (1).mkv` already present, a legal `keep_both` upload chose the occupied `(1)` path and
  ended `FAILED/upload_write_failed` instead of creating `(2)`. This violates Slice RO-6, the Slice
  Upload conflict contract and this Task's explicit backend-named keep-both Acceptance Criterion.
  A generated keep-both destination must be absent; preserve directory-merge behavior at its
  separate boundary and add repeated-suffix collision coverage for files and directory nodes.
- **P1 — An admitted Upload loses its pinned Active execution path after a normal configuration
  activation.** Each item request refreshes the API binding, but `_admitted` exists only on the old
  `DirectFileUploadService`; after admitting under revision A and activating a valid revision B,
  the next item request through B reproduced `files_upload_unknown` while the durable Task still
  names revision A. This breaks the current Files Upload journey while its Task remains visible and
  violates Slice RO-6/RO-9 plus this Task's pinned-Active Acceptance Criterion. Keep a bounded
  task-keyed Upload Session registry above the replaceable runtime binding; each entry owns the
  already-validated plan and exact pinned binding from admission through terminal cleanup, so a new
  Active affects new uploads only. Do not add a resumable/chunk protocol or schema migration. A
  genuinely lost in-process session must fail with an explicit interrupted/resubmit recovery rather
  than `not_found`. Cover activation between admission, item streaming and finish.
- **P1 — The per-item API does not enforce that the HTTP body length equals the admitted item
  size.** A manifest declaring two bytes followed by an item request with `Content-Length: 7` and body
  `abEXTRA` returned `SUCCESS`, persisted `ab`, and silently ignored the excess bytes; the same route
  also accepts an absent `Content-Length` instead of failing closed. This is a current authenticated
  API journey with a false success outcome and violates the Slice Upload request/file limits plus
  this Task's over-limit and bounded API/Web Acceptance Criteria. Reject a mismatched or unprovably
  bounded item body before mutation, retain short-body truth, and test shorter, exact, longer and
  missing/invalid length through the WSGI route.
- **P1 — Archive Download fabricates success when a current Storage read fails after an entry has
  started.** `_ArchiveProducer._run` swallows the provider exception, so a fault-injecting current
  Storage that returned two bytes and then disconnected produced a valid ZIP containing the
  truncated `tree/a.bin == b"ab"` with no archive manifest at all. Current SMB/OpenList/S3 reads can
  fail this way; the operator receives incomplete content without the required per-item failure or
  recovery evidence. This violates Slice RO-6/RO-9 and this Task's truthful mid-stream-change and
  interrupted-transfer Acceptance Criteria. Keep the bounded producer, but make its queue protocol
  explicit (`data` / `entry failure` / `terminal error` / `done`) and never swallow producer
  exceptions. A recoverable per-entry read failure must close that entry and append a failed
  manifest outcome; if ZIP integrity or the manifest can no longer be guaranteed, abort the response
  as a terminal transfer failure instead of emitting a success-looking archive. Cover a mid-entry
  provider failure after response bytes have begun.
