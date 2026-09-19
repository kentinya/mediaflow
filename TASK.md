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

## B Review Result

```text
Reviewed: eeac5849b5489f91c26601b9878da5303879377d..1d5af5f507b0c1dcc4894cbab775598ced3734f8
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The Web Upload entry point cannot send its production request. `uploadFiles` supplies a
  `ReadableStream` body without the browser-required `duplex` request option and depends on a
  script-set `Content-Length`; Chromium rejects the former before network I/O and strips the latter
  even when `duplex` is supplied, while `_files_upload_manifest` requires that header. This breaks
  the authorized `/ui-v2/library/files` Upload journey and the API/Web shared behavior acceptance.
  Replace the framing/transport with a browser-compatible bounded streaming request that still
  proves count/depth/per-file/aggregate/request limits before the first Storage mutation, and add a
  real-browser-to-WSGI integration test rather than a permissive mocked `fetch` test.
- A pre-decided no-overwrite/skip conflict returns from `_execute_item` without consuming that
  item's declared payload. The next sibling therefore reads the conflicting item's bytes and may be
  recorded `SUCCESS` with corrupted content; the endpoint then detects leftover bytes only after
  mutation. Reproduction with `existing.mkv=blocked` followed by `ok.mkv=ok` produced
  `ok.mkv == b"bl"` and left `b"ockedok"` unread. This violates independent per-item outcomes,
  truthful success and data-integrity recovery. Keep payload framing aligned for every outcome,
  ensure post-mutation framing failures cannot conceal known effects, and cover an actual framed API
  request whose first item conflicts and whose later sibling's exact bytes still succeed.
- Archive Download is not streamed within bounded memory. `_archive_file_entry` writes a complete
  file into `_ZipStreamSink._chunks`, and `stream_archive` drains only after that method returns; a
  4 MiB legal file was fully read before the first 39-byte response chunk was yielded. At the
  current 20 GiB bound this can exhaust the server and break directory/multi-selection Download.
  Drain ZIP output while each file is being read and add a test proving source consumption before
  the first/next response chunk remains bounded independently of file size.
- Download admission pins only path and size. A same-size source replacement after admission is
  streamed as if it were the admitted entry and the archive manifest records `included`; replacing
  `AAAA` with `BBBB` reproduced an archive containing `BBBB` with a successful manifest item. This
  violates the required truthful handling of sources that change during streaming. Pin and
  revalidate sufficient provider-neutral entry evidence at the read boundary (without weakening
  confinement or zero-mutation behavior), and cover same-size replacement as well as shrink/vanish.
- Multi-file/directory Upload does not expose the promised durable progress or safe pause/cancel
  journey. The API creates the Task and runs `_execute` synchronously before returning its ID, while
  Files shows only a whole-request spinner and has no Task polling or lifecycle actions; an operator
  cannot use the normal Web journey to observe per-item progress or pause/cancel at safe item
  boundaries. Connect admission/execution and Files to an observable durable Task lifecycle with
  truthful terminal/recovery state, and cover progress plus pause/cancel through the production Web
  path.
