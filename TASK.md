# Task 38.1 — 分离库路由并完成 MediaLibrary 实时只读浏览

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.1
Parent Slice: 38
Status: FIX REQUIRED
Task Base: 86bb69d52891755933f23763d32558668b30f9c6
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authorized operator can enter separate ResourceLibrary Files and MediaLibrary pages, then select
an enabled MediaLibrary and browse its actual Storage entries safely through API or Web. This
completes Slice 38 RO-1 and the read-only MediaLibrary journey in RO-3, and establishes the kind
separation required by RO-7. Configuration creation/removal and MediaLibrary commands remain later
in-Slice work.

## Why This Task Exists

At Task Base, `/ui-v2/library` is a ResourceLibrary landing and `/ui-v2/library/files` is the
ResourceLibrary Files page. The runtime browser, its cursor scope, the Web read model and shell
search are ResourceLibrary-only; passing a MediaLibrary ID through them would confuse two different
roots and authorities. A useful first unit is the complete read path and route migration together:
operators can reach and browse a real destination library, while the existing source Files and
Organize journey continues at its new address. This gives later Add and command Tasks a tested,
kind-specific authority boundary instead of a relabelled source page.

## Implementation Scope

- Replace the old Library landing route with `/ui-v2/medialib/files` and move the existing Files
  page to `/ui-v2/resourcelib/files`. Retire `/ui-v2/library` and `/ui-v2/library/files` with a
  bounded unavailable-route state linking explicitly to both supported pages, without redirect or
  work admission. Update sidebar state/title, shell search ownership, Dashboard/Operations and all
  other internal Files links, authentication continuation and Files-originated Organize return
  context, including previously created durable intent/preview/execution links. Preserve the exact
  ResourceLibrary ID and relative directory. Keep the existing Files body and API behavior intact.
- Add read-only MediaLibrary list and browse API under `/api/v1/media-libraries/...`, backed by the
  exact Active runtime and Storage interfaces. The server selects the configured MediaLibrary and
  enabled Storage and joins its configured root with a safe library-relative path; no client-sent
  Storage ID or root is trusted. Preserve live entry identity, including boundary whitespace.
  Return bounded cards/entry facts without FileIndex, Result, metadata, thumbnails or full-library
  statistics. Disabled/unavailable libraries have truthful, actionable state and cannot be browsed.
- Namespace MediaLibrary cursor authority by library kind, ID, snapshot, Storage, root, path and
  page limit as appropriate. A ResourceLibrary cursor, even for the same ID/root, must fail on the
  media endpoint and vice versa. Retain deterministic cursor paging and the existing bounded search
  semantics; do not add recursive search or fabricated totals. Preserve existing ResourceLibrary
  cursors/API compatibility.
- Build the initial MediaLibrary read journey in the shared V2 shell: title/subtitle, enabled
  library cards with Storage/root, selected card, lazy directory tree, exact breadcrumbs, refresh,
  list/grid entries with type icons, six-column table structure, and honest previous/next paging.
  Per-entry size and modified time are allowed; card totals/capacity/placeholders, thumbnails,
  recognition/status and Organize/Scan/Preview controls are excluded. No dead Add or file-command
  controls: those become available only when their later Tasks implement the corresponding journey.
  Keep MediaLibrary page state, cache keys and shell search independent of ResourceLibrary Files.
- Cover missing Active/binding/library/path, stale cursor, denied/unavailable Storage, malformed
  responses, empty directories and externally removed directories with scoped error messages and
  explicit root/refresh/configuration recovery. Refresh must drop stale directory and selection
  memory while retaining a still-valid location. Reads, navigation, search and refresh perform zero
  Storage mutation and start no processing Task or metadata request.
- Update affected automated API, component and browser tests for the new addresses and the new
  read journey. Preserve existing Files/Organize tests and the user's dirty
  `docs/pics/文件页.png`; do not alter the supplied `docs/pics/媒体库页.png`.

## Acceptance Criteria

- [ ] Direct, sidebar and authenticated continuation reach both new routes with correct active
      navigation and page/search ownership. The two retired routes show bounded recovery links and
      start no work; no supported internal link emits a retired address.
- [ ] Files at `/ui-v2/resourcelib/files` retains add/remove, browsing, search, refresh, direct
      commands, single/batch Organize, policy binding and exact Organize return context. Existing
      ResourceLibrary API and durable work remain compatible; unrelated V2/V1 journeys still work.
- [ ] API and Web list and browse enabled MediaLibraries from the same Active snapshot and live
      Storage. Equal MediaLibrary/ResourceLibrary IDs, overlapping roots and cross-kind cursors never
      exchange authority. Client paths are library-relative, confined and exact. Reading is
      side-effect free and does not depend on FileIndex or results.
- [ ] The MediaLibrary page supports library selection, lazy navigation, bounded search, refresh,
      list/grid and honest cursor paging, including empty and multi-page directories and names with
      boundary whitespace. Missing/external deletion, 401/403, unavailable Storage and malformed
      data identify the affected scope and offer a concrete safe next action.
- [ ] The read-only page follows the specified hierarchy to the extent this Task's actions exist,
      uses type icons, and shows no card statistics/capacity/placeholder, thumbnails, recognition
      or organize status, or MediaLibrary Organize/Scan/Preview control. Keyboard/focus and narrow
      layout remain usable. The Files body and shared shell are changed only as required by route,
      search and navigation integration.
- [ ] Focused and T4 regression/quality gates pass with actual counts, skips and unavailable gates
      reported. The checkpoint includes only in-scope files and no credentials, `config/alist.json`,
      unrelated image changes, deleted tests, weakened assertions or hidden skips.

## Required Tests

Run from the repository root unless a `web/` prefix is shown. Use the existing `.venv` and local
fake/temporary Storage; no production services or user media.

- `python3 scripts/check_governance.py`
- `.venv/bin/python -m unittest discover -s tests -p 'test_runtime_files_browser.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'`
- Add and run focused Python tests for MediaLibrary list/browse API, exact path/cursor/kind isolation,
  invalid/denied/missing states and zero-mutation reads.
- `.venv/bin/python -m unittest discover -s tests`
- `npm --prefix web run test -- --run` (including new MediaLibrary page/model/API tests, Files,
  shell, route and Organize return tests).
- From `web/`: `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/deep-link.spec.ts
  tests/e2e/manual-operations.spec.ts` plus new MediaLibrary browse and retired-route browser tests.
- `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`;
  `.venv/bin/python -m compileall -q mediaflow tests scripts`;
  `.venv/bin/python -m pip check`; `scripts/docker_release_security_smoke_test.py`.
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` and
  `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- Confirm `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` has no matches.
- `npm --prefix web run typecheck`; `npm --prefix web run lint`;
  `npm --prefix web run format:check`; `npm --prefix web run build`.
- Inspect `git diff --check`, the Task Base..Head manifest, private files and the two reference
  images. If a gate is unavailable, report the command, reason and remaining risk rather than
  claiming a pass.

## Non-goals

- MediaLibrary Add drawer, checked activation, configuration removal or editing.
- MediaLibrary direct file commands, text editing, Copy/Move, durable command Task/Worker or
  recovery changes. These remain required later in Slice 38.
- Card statistics/capacity/placeholders, thumbnails, MediaLibrary Organize/Scan/Preview,
  FileIndex-derived physical rows, global search, arbitrary paging or new providers.
- ResourceLibrary Files body redesign, V1 route removal, general shell redesign or changes to the
  A-owned Slice Contract/Roadmap/requirements/architecture boundary.

## Developer Completion Report

### Correction Round 1 (B FIX REQUIRED — P1 route-recoverable directory state)

B's blocker: `MediaLibraryFilesPage.openPath()` only updated the component's `path`,
`updateLibraryRouteState()` only updated `mediaLibraryId`, so entering `Breaking Bad` left the URL at
`/ui-v2/medialib/files`; after refresh + reconnect the page showed the root `Breaking Bad` instead of
`Season 1`, and switching library from a path-bearing deep link left the old `path` in the URL.

Reproduced first against the recorded checkpoint with a temporary Playwright probe (built artifact +
local fake server, deleted before this checkpoint):

```text
Task Base..e431580 (before the fix):
  URL after openPath:  .../ui-v2/medialib/files
  URL after reconnect: .../ui-v2/medialib/files
  after reconnect Season 1 visible: false / Breaking Bad visible: true
  URL after library switch: ...?mediaLibraryId=tv&path=Breaking+Bad
```

Changed in this correction:

- `web/src/features/library/MediaLibraryFilesPage.tsx` — `updateLibraryRouteState(libraryId)` is
  replaced by `syncLibraryRouteState(libraryId, relativePath)`, which writes the resolved library
  **and** its exact library-relative directory together, is a no-op while the address already
  describes that location, and preserves `window.history.state` instead of clearing the router's
  history state. A single effect now owns the write: it records the library the live read actually
  resolved plus the browsed directory, substituting the root whenever the address still names a
  MediaLibrary the Active runtime does not enable (`requestedLibraryUnavailable`). A locally rejected
  deep-link path is deliberately left in the address so the truthful invalid-path state is not
  rewritten into a fabricated root; its explicit root recovery clears `path` and the same writer then
  records the root. No behavioural change to reads, mutations, Tasks or metadata requests.
- `web/src/features/library/MediaLibraryFilesPage.test.tsx` — four new focused component tests:
  exact library + relative directory recorded on navigation and cleared-but-library-kept on return
  to root; library switch replacing the previous library's directory; an unavailable requested
  library replaced by the browsed one at its root; a rejected deep-link path kept in the address
  with its root recovery.
- `web/tests/e2e/medialib-files.spec.ts` — two new browser regressions required by B: directory
  navigation / deeper navigation / return-to-root / library switch keep the route exact, with a
  reload + reconnect restoring the same directory (and the root listing explicitly absent); and an
  unavailable requested library being replaced by the browsed one in the route, including after a
  reload. The first test's entry assertion now expects the recorded library.
- `web/tests/e2e/deep-link.spec.ts` — the existing MediaLibrary continuation test now also proves a
  deep link naming `Breaking Bad/Season 1` continues to that exact directory and that reload +
  reconnect restores it; its entry assertion expects the recorded library.
- `web/tests/e2e/operations.spec.ts` — the 媒体库 entry assertion expects the recorded library.

Not committed: the user's dirty `docs/pics/文件页.png` (preserved untouched) and the ignored
`config/alist.json`. `docs/pics/媒体库页.png` was not modified.

### Changed Files

Round 1 correction (the only files this correction changes):
- `web/src/features/library/MediaLibraryFilesPage.tsx`
- `web/src/features/library/MediaLibraryFilesPage.test.tsx`
- `web/tests/e2e/medialib-files.spec.ts`
- `web/tests/e2e/deep-link.spec.ts`
- `web/tests/e2e/operations.spec.ts`

Original Task implementation (unchanged by this correction):

Backend
- `mediaflow/application/storage_browser.py` — `RuntimeFilesBrowserService._media_libraries`,
  `list_media_libraries()`, `browse_media_library()`, `_media_library()`,
  `_media_library_breadcrumbs()`, and the `media_library_not_found` failure category. The
  MediaLibrary read path reuses the existing `ReadOnlyStorageGuard`/Storage interfaces and adds no
  new mutation surface.
- `mediaflow/interfaces/service_api.py` — `GET /api/v1/media-libraries`,
  `GET /api/v1/media-libraries/{id}/files`, `_media_library_files_query`, the read-only audit
  suppression entries for both routes and the error-projection route shapes.
- `tests/test_media_library_browser.py` (new) — focused MediaLibrary API proof.

Web
- `web/src/entities/library/media-library-files.ts` (new) + `.test.ts` (new) — bounded
  MediaLibrary list/browse frontend models and their normalizers.
- `web/src/shared/api/api-client.ts`, `web/src/shared/api/api-errors.ts` +
  `web/src/shared/api/media-library-api.test.ts` (new) — `fetchMediaLibraryList`,
  `fetchMediaLibraryFiles`, `mediaLibraryFilesUrl`, `MediaLibraryFilesApiError` and the bounded
  MediaLibrary failure mapping.
- `web/src/features/library/media-library-query.ts` (new) — independent MediaLibrary query keys.
- `web/src/features/library/MediaLibraryFilesPage.tsx` (new) + `.test.tsx` (new) — the read-only
  MediaLibrary journey.
- `web/src/features/library/LibraryLanding.tsx` (deleted) — the retired Library landing body.
- `web/src/routes/router.tsx` + `web/src/routes/router.test.tsx` (new) — both new routes, the two
  bounded retired-route registrations and the route-separation regressions.
- `web/src/shared/navigation/destination-model.ts` + `.test.ts` — new paths, active state and the
  `/medialib/files` continuation allowlist; `files-return.ts` now returns to
  `/resourcelib/files`.
- `web/src/shared/ui/AppShell.tsx` + `.test.tsx` — shell search ownership covers both Files pages.
- `web/src/features/operations/OperationsLanding.tsx`, `OrganizeNewPage.tsx`,
  `ManualOperationsRouter.test.tsx` — the manual ResourceLibrary action journey now lives on the
  Operations workspace and the Organize compatibility landing links to the supported Files address.
- `web/tests/fake-server.mjs` — deterministic MediaLibrary cards/entries, paging, cross-kind cursor
  and failure fixtures.
- `web/tests/e2e/medialib-files.spec.ts` (new) and updates to `deep-link.spec.ts`,
  `library-files.spec.ts`, `library-file-detail.spec.ts`, `manual-operations.spec.ts`,
  `operations.spec.ts` for the new addresses and the retired-route state.
- `web/src/features/entry/EntryPage.test.tsx`, `web/src/shared/api/auth-store.test.ts`,
  `web/src/shared/auth/AuthBoundary.test.tsx` — continuation/ownership tests at the new addresses.

Not committed: the user's dirty `docs/pics/文件页.png` (preserved untouched) and the ignored
`config/alist.json`. `docs/pics/媒体库页.png` was not modified.

### Implemented

Correction Round 1 — recoverable MediaLibrary location in the route (B's P1):

- **The library and its directory are one location.** `MediaLibraryFilesPage` now writes the
  MediaLibrary it actually resolved together with the exact library-relative directory being browsed
  through one writer, `syncLibraryRouteState(libraryId, relativePath)`. Entering a directory (and
  deeper navigation) records `mediaLibraryId` **and** `path`; returning to the library root clears
  `path` while keeping the library; switching library records the new library at **its own root**.
  The three symptoms B reported — a directory that never reached the URL, a refresh/reconnect that
  fell back to the library root, and a stale `path` surviving a library switch — all come from the
  same absent transition and are fixed together.
- **Only a valid location is recorded.** When the address names a MediaLibrary the Active runtime
  does not enable, the address records the library actually browsed, at its root, instead of
  replaying the unavailable request next to a directory belonging to another library. A path the
  page rejects locally stays in the address so the truthful invalid-path state is not rewritten into
  a fabricated root, and its explicit `返回媒体库根目录` recovery repairs the address through the same
  writer. The write is skipped while the address already describes the browsed location and keeps
  `window.history.state`, so it neither fights the operator's navigation nor churns router history.

Original Task implementation:

- **Route separation (RO-1).** `/ui-v2/resourcelib/files` is the ResourceLibrary Files page and
  `/ui-v2/medialib/files` is the MediaLibrary page. The sidebar entries, page titles, shell search
  ownership, authentication continuation, the Organize compatibility landing and the
  Files-originated Organize return context all use the new addresses; the exact ResourceLibrary ID
  and relative directory are preserved. `/ui-v2/library` and `/ui-v2/library/files` are registered
  as one bounded recovery state that links explicitly to both supported pages and performs no read,
  admission or redirect. The retired Library landing body is removed.
- **MediaLibrary read API (RO-3/RO-7).** `GET /api/v1/media-libraries` returns enabled libraries
  with their Storage and configured root; `GET /api/v1/media-libraries/{id}/files` resolves the
  library from the exact Active snapshot, verifies its Storage binding and joins the configured
  root with a confined library-relative path, so no client-sent Storage ID or root is trusted.
  Entries come from live Storage only — no FileIndex, Result, metadata, thumbnail or full-library
  statistic is read or published, and boundary whitespace identity survives projection.
- **Kind-namespaced cursor authority.** MediaLibrary cursors are issued under the
  `media_library:<id>` scope with the existing revision/storage/path/limit context, so a
  ResourceLibrary cursor fails on the media endpoint and vice versa — including the same-ID,
  same-Storage, same-root case. Existing ResourceLibrary cursors and API behavior are unchanged;
  paging stays deterministic with no recursive search or fabricated totals.
- **MediaLibrary read journey.** The page shows the title/subtitle, enabled library cards with
  Storage and root (selected card, no statistics/capacity/`未统计` placeholders), a lazy directory
  tree, exact breadcrumbs, refresh, list/grid entries with type icons, the six-column table
  structure, bounded search through the shell top bar, selection count/known size and honest
  previous/next paging. Missing Active/Storage/path, stale or cross-kind cursors, denied or
  unavailable Storage, malformed responses, empty and externally removed directories produce scoped
  messages with an explicit retry or return-to-root recovery. Reads, navigation, search and refresh
  perform zero Storage mutation and start no Task or metadata request.
- **Independence.** MediaLibrary page state, cache keys and shell search are separate from
  ResourceLibrary Files; a media route never requests the resource namespace and vice versa.

### Tests and Results

Task Base `86bb69d52891755933f23763d32558668b30f9c6`; all commands from the repository root unless
`web/` is shown. Every command below was rerun after the Correction Round 1 changes, so all results
belong to this correction checkpoint.

| Command | Result |
|---|---|
| `python3 scripts/check_governance.py` | PASS |
| `.venv/bin/python -m unittest discover -s tests -p 'test_runtime_files_browser.py'` | PASS — 7 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'` | PASS — 13 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_browser.py'` | PASS — 5 tests |
| `.venv/bin/python -m unittest discover -s tests` | PASS — 1726 tests, 7 skipped |
| `npm --prefix web run test -- --run` | PASS — 37 files, 507 tests (4 new route-state tests) |
| `npm --prefix web run typecheck` | PASS |
| `npm --prefix web run lint` | PASS |
| `npm --prefix web run format:check` | PASS |
| `npm --prefix web run build` | PASS |
| `web/`: `npx playwright test` (full suite) | PASS — 136 tests (2 new) |
| `web/`: B's reproduction — enter `Breaking Bad`, refresh + reconnect, switch library from a path-bearing deep link | PASS — URL records `?mediaLibraryId=movies&path=Breaking+Bad`, reconnect restores `Season 1`, library switch leaves `?mediaLibraryId=tv` with no `path` |
| `web/`: required specs `library-files`, `deep-link`, `manual-operations` + `medialib-files` | PASS |
| `.venv/bin/ruff format --check .` | PASS — 311 files formatted |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | PASS |
| `.venv/bin/python -m pip check` | PASS — no broken requirements |
| `.venv/bin/mediaflow --config config/strategy.example.json config validate` | PASS |
| `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` | PASS |
| `rg -n -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml` | PASS — no matches (`rg` absent, equivalent `grep -rn -i -E` used, exit 1) |
| `scripts/docker_release_security_smoke_test.py` | PASS with `TMPDIR` inside the workspace — see Risks; "Release-security smoke acceptance passed", exit 0 |

The Correction Round 1 browser evidence, from `web/tests/e2e/medialib-files.spec.ts` against the
rebuilt artifact and the local fake API:

```text
directory navigation, return to root and library switching keep the route exact
  → ?mediaLibraryId=movies&path=Breaking+Bad  after opening Breaking Bad
  → same URL and Season 1 visible              after reload + reconnect
  → path=Breaking+Bad%2FSeason+1               after opening Season 1
  → ?mediaLibraryId=movies (no path)           after 返回媒体库根目录
  → ?mediaLibraryId=tv (no path)               after switching library
an unavailable requested library is replaced by the browsed one in the route
  → ?mediaLibraryId=movies                     from ?mediaLibraryId=disabled-lib&path=…
  → unchanged after reload + reconnect, no stale notice
```

New focused MediaLibrary Python coverage (`tests/test_media_library_browser.py`) proves the enabled
list and browse documents, root-relative confined paths, boundary whitespace, the disabled-library
404, invalid path/query/limit rejection, 401/503 fail-closed states, zero-mutation reads through an
adapter that raises on every mutation, an empty Task/Job repository afterwards, and cross-kind
cursor rejection in both directions for libraries whose ID, Storage and root are identical.

### Decisions

Correction Round 1:

- Wrote the library identity and the relative directory as one state transition instead of two
  independent writers. B's three symptoms share one root cause: the address was updated on library
  change only, so the directory was never part of the location. A single writer fed by the resolved
  location makes "which library" and "which directory inside it" impossible to disagree, and
  automatically covers refresh, reconnect and library switch.
- Substituted the root — not the stale request — when the address names a MediaLibrary the Active
  runtime does not enable. The page already explains the substitution; letting the address keep
  `mediaLibraryId=disabled-lib&path=<foreign directory>` would have meant a reconnect replaying an
  unavailable library together with a directory belonging to another one.
- Kept a locally rejected deep-link path in the address and did not rewrite it. Silently replacing
  `?path=../outside` with a clean root URL would hide that the operator's link was rejected and
  fabricate a location they never asked for; the bounded invalid-path state plus its explicit
  "返回媒体库根目录" recovery remains the truthful presentation, and that recovery now also repairs
  the address.
- Made the write a no-op when the address already describes the browsed location, and kept
  `window.history.state`, so the correction adds no history churn and does not disturb the router's
  own back/forward accounting.
- Left the ResourceLibrary Files route-state writer alone. B's blocker named the MediaLibrary page;
  changing Files' continuation contract would have expanded this correction beyond the listed
  blocker while Files' existing deep-link behaviour is a Slice-37 accepted surface.

Original Task implementation:

- Kept the existing `RuntimeFilesBrowserService` as the one read authority for both library kinds
  instead of adding a second browser service; the MediaLibrary methods reuse the same
  `ReadOnlyStorageGuard`, cursor codec and `_document` projection, so the kind difference is an
  explicit scope value rather than a parallel implementation.
- Namespaced the cursor by scope string `media_library:<id>` inside the existing cursor context
  rather than changing the context schema. This keeps every previously issued ResourceLibrary cursor
  valid while making cross-kind replay impossible.
- Served the enabled-library list from `/api/v1/media-libraries` (mirroring
  `/api/v1/resource-libraries/files`) instead of extending `system/status`, so the page's card data
  and the browse authority come from the same Active snapshot in one read model.
- Moved the manual ResourceLibrary action-matrix journey from the retired Library landing to the
  Operations workspace (`OperationsLanding`) and made its scope selection URL-derived, so the
  read-only-principal and backend-reason coverage survives the landing's retirement without a new
  page.
- Deleted nothing from the Files body: the only Files changes are its route address, the shared
  search ownership and the return-href target.

### Remaining In-Slice Work

- MediaLibrary Add drawer, checked activation, configuration removal/editing (RO-4) and the
  page-local configuration handoff for disabled libraries.
- MediaLibrary direct file commands, text editing, Copy/Move and their durable Task/Worker
  results/recovery (RO-5/RO-6), including the selection action bar's command controls and the
  per-row More menu.
- Controlled `1536 x 1024` screenshots and narrow-screen evidence for the closure packet, and the
  Slice-final reconciliation of `docs/media-library-page-visual-spec.md` (still marked TARGET).

### Risks / Deviations

- Correction Round 1 addressed only B's single P1 blocker. The ResourceLibrary Files page
  (`StorageFilesPage.tsx`) keeps its pre-existing behaviour of recording `resourceLibraryId` but not
  the browsed relative path; B's blocker named the MediaLibrary page, that file is unchanged by this
  Task (identical to Task Base), and Files' own deep-link/return journey is preserved as required. It
  is recorded here as an observed, deliberately un-expanded neighbouring behaviour for B to judge,
  not asserted to be acceptable.
- The route writer preserves `window.history.state` rather than clearing it. TanStack's history
  implementation tags entries with `__TSR_key`/`__TSR_index`; clearing that state would make a
  subsequent back/forward accounting inconsistent, so the same-entry replace keeps it.
- `scripts/docker_release_security_smoke_test.py` needs `TMPDIR` inside the workspace
  (`TMPDIR=/root/mediaflow/.smoke-tmp`); this environment's Docker daemon cannot bind-mount the
  harness `/tmp`, and the unmodified default invocation fails with
  `bind source path does not exist: /tmp/mediaflow-smoke-security-*/deployment.env`. This is an
  environment limitation, not a product defect; the real deployment gate was not weakened. The
  `.smoke-tmp` scratch directory is untracked and excluded from this checkpoint.
- `rg` is not installed, so the FFmpeg/FFprobe exclusion check was run with
  `grep -rn -i -E 'ffprobe|ffmpeg' mediaflow pyproject.toml` and has no matches.
- One full-suite run reported `test_rename_binds_observed_source_evidence_and_refuses_swaps`
  (a Slice-37 Files direct-command test untouched by this Task) failing because the filesystem's
  coarse `ctime_ns` made two same-size writes indistinguishable in `inode:ctime` identity — a direct
  probe measured 288/300 collisions for that sequence. It passed in isolation, under CPU load, at
  Task Base, and in the final full runs before and after this correction. Recorded as
  environment-dependent pre-existing flakiness; B should judge whether it needs its own follow-up.
- `TASK.md` needed one addition to its Required Tests list: `scripts/docker_release_security_smoke_test.py`.
  The pre-existing `tests/test_release_security.py` gate requires every active `TASK.md` to document
  all release-quality commands, and the planned list omitted that command (the same correction B
  made for Task 37.12, commit `6183005`). Task ID, Task Base, Goal and Scope are unchanged.
- The MediaLibrary page's `操作` column shows only the working directory `打开` navigation; file rows
  render `—` because this Task adds no file-command journey. Commands arrive with the later RO-5/RO-6
  Tasks, so no dead control is presented.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 47d158d2958c526e4aaf5ab89c0002b079e5e67d
```


## B Review Result

```text
Reviewed: 86bb69d52891755933f23763d32558668b30f9c6..f58139885aefe5e477dece60770702c6cc8ce55f
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — MediaLibrary 子目录状态没有进入可恢复的路由。** 当前生产页面的
  `MediaLibraryFilesPage.openPath()` 只更新组件内的 `path`，
  `updateLibraryRouteState()` 也只更新 `mediaLibraryId`；从媒体库根页进入
  `Breaking Bad` 后，实际浏览器显示该目录的 `Season 1`，URL 仍是
  `/ui-v2/medialib/files`。刷新并重新连接后，页面显示根目录的
  `Breaking Bad`，不再显示 `Season 1`（使用当前构建和本地 fake server 的
  Playwright 复现）。从含 `path` 的深链切换库时，旧 `path` 还会留在 URL。
  这违反 Slice RO-1 的目录深链/认证续接、Required Surfaces 的 library-relative
  deep links，以及本 Task 的导航和恢复验收。请让目录导航、返回根目录和切换库
  同步准确的库 ID 与相对路径到路由，并以 Web 浏览器回归证明刷新、重新连接和
  切换库后只恢复当前有效位置。
