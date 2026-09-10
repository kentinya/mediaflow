# Task 32.2 — V2 FileIndex discovery journey

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 32.2
Parent Slice: 32
Status: READY FOR B REVIEW
Task Base: 4b1f8358199a6eaf00f043175c17eccedf0d7083
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Complete the FileIndex catalog portion of Slice 32: an authenticated operator can open a real V2
FileIndex route, inspect bounded durable discovery records, submit/reset/revisit meaningful search
and filters, move through deterministic pages, and understand discovery/stability, current
occurrence and processing disposition as distinct facts without starting work. This completes RO-3
and advances RO-1 and RO-6 through RO-8.

## Why This Task Exists

Task 32.1 made `/ui-v2/library` and the Active Storage Files journey real, but its FileIndex choice
still hands off to the current V1 Web UI. The authoritative Python catalog already provides
authenticated read-only list/search/filter behavior at `GET /api/v1/file-index`, stable
`updatedAt`/`fileId` cursor components, bounded records, current occurrence state and processing
disposition. V2 has no typed entity/query model or catalog route for that behavior. The API also
lacks a server-side processing-disposition filter, so filtering that field in the browser would
misrepresent a bounded page as the catalog result.

The catalog route, minimal authoritative filter completion, typed normalization, submitted filter
state, paging, failure recovery and built-artifact proof form one independently useful vertical
journey. File detail and physical/indexed detail linkage require a materially richer projection and
remain a later coherent Task; splitting individual filters, labels or test cases would be too small.

## Implementation Scope

The implementation boundary is:

```text
FileIndex Domain/Persistence filter
→ existing FileCatalog Application/API authority
→ typed V2 entity/API/query boundary
→ Library FileIndex route/view
→ unit/integration/router/browser regressions
```

- Replace the Library landing's FileIndex V1 continuation with a real, shell-integrated,
  refresh-safe V2 catalog route under `/library`. Keep an explicit current V1 Web continuation only
  for operational or detail actions not implemented by this Task; do not claim those actions work
  in V2.
- Add one bounded `processingDisposition` FileIndex filter through the existing domain/application,
  in-memory/SQLite persistence and `/api/v1/file-index` list authority. Validate supported values,
  preserve existing aliases and response compatibility, and apply the filter before paging. Do not
  implement it as client-side filtering of a returned page or introduce another endpoint.
- Add strict centralized V2 normalization for the FileIndex list document and the allowlisted record
  facts needed here: safe identifiers, Storage-relative path/filename, discovery status/change and
  stability timestamps, current occurrence state, processing disposition, bounded identity summary,
  update timestamp and paging inputs. Ignore unknown fields and fail the whole malformed document
  closed; do not expose fingerprints, absolute roots, raw provider payloads or detail-only evidence.
- Build feature-owned TanStack Query options and URL construction for authenticated bounded GETs.
  Search and applied filters may use allowlisted route state so refresh/back is useful; use only
  backend-supported query names and safe scalar values, never credentials or execution authority.
- Build an operator-oriented filter form with a clearly separate draft and submitted state. Include
  path/filename search plus applicable ResourceLibrary, Storage, discovery-status,
  processing-disposition and existing identity filters. Populate Storage/ResourceLibrary choices
  from the exact managed Active System Status projection with operator labels where available; raw
  IDs may appear secondarily for diagnosis but must not be required to reach the first useful page.
  Submitting or resetting filters resets paging deterministically.
- Render bounded catalog rows/cards that visibly separate discovery/stability/change evidence,
  current occurrence state and processing disposition. Missing/unverified facts remain explicit;
  do not infer a successful outcome, current Result relevance or action eligibility from path,
  membership or historical data.
- Implement deterministic next/previous/back behavior using the backend's stable
  `updatedAt` + `fileId` cursor contract. A bounded one-record lookahead may establish whether a next
  page exists; do not invent opaque cursors, recursively load the catalog, silently refetch every
  page or expose cursor components as ordinary operator ceremony. Preserve submitted filters while
  paging and useful prior context when returning to Library.
- Keep loading, empty-unfiltered, empty-filtered, no managed Active options, invalid/unknown filter,
  invalid/stale cursor, unavailable/malformed catalog, 401 and RBAC 403 states inside the shell with
  the smallest truthful retry, reset, previous-page, reconnect or V1 Configuration continuation.
  Never render raw exception/API/provider text or private paths.
- Keep all catalog entry, search, filter, page, refresh and retry requests read-only. They must not
  call detail or by-source speculatively, access Storage/media content, invoke Providers, submit
  Scan/Preview/Organize/Reprocess/review work, create audit mutations or send a non-GET API request.
- Add responsive and keyboard-usable presentation using the existing shell/UI foundation. Preserve
  Task 32.1 Storage Files behavior, V1 `/ui`, Dashboard and the remaining migration surfaces.
- Extend the Playwright fake only with secret-free FileIndex GET fixtures and bounded failures. It
  must reject unsupported methods and must not log or persist Bearer values.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, stable requirements and every A-owned Contract field.
- FileIndex detail/explanation, occurrence/history expansion, reviews/checkpoints, current/historical
  Result explanation and physical-to-indexed detail navigation; these remain the next coherent work
  within Slice 32.
- Storage Files semantics, Active activation/configuration editing, operational/recovery mutations,
  OrganizerExecutor and all POST/PUT/PATCH/DELETE authorities.
- New FileIndex schema/lifecycle design, full-text search infrastructure, Provider calls and V1
  behavior beyond the minimal backward-compatible processing-disposition list filter.

## Acceptance Criteria

- [ ] `/ui-v2/library` opens a real FileIndex catalog route that remains correctly titled and active
      in the shared shell across direct entry, refresh and memory-only auth continuation. Storage
      files and durable FileIndex stay visibly distinct, and no unfinished detail/action control is
      presented as implemented V2 behavior.
- [ ] A valid managed Active runtime yields operator-labeled Storage/ResourceLibrary choices and a
      first bounded FileIndex page without requiring the operator to type an internal ID. Draft or
      stale configuration is not presented as Active filter authority.
- [ ] The operator can submit meaningful path/filename search and applicable ResourceLibrary,
      Storage, discovery, processing and identity filters; the submitted state is visible,
      refresh-safe and distinct from unsubmitted edits, while reset restores the unfiltered first
      page and removes stale cursor state.
- [ ] `processingDisposition` is validated and applied by the authoritative FileCatalog query before
      paging across supported persistence implementations. Existing list filters, aliases, RBAC,
      redaction and malformed/duplicate/unsupported-query behavior remain compatible.
- [ ] Each result keeps discovery status, stability/change evidence, current occurrence state and
      processing disposition in separate operator-language groups. Missing, unverified, legacy or
      absent identity facts are not guessed and no historical Result is portrayed as current solely
      from this list projection.
- [ ] Next and previous/back movement is deterministic and bounded under the submitted query, uses
      the existing stable cursor components, preserves useful filter context, and does not duplicate,
      skip or recursively enumerate records in the covered equal-timestamp/page-boundary cases.
- [ ] Loading, unfiltered empty, filtered empty, no managed Active options, invalid/unknown filters,
      invalid/stale cursor, malformed/unavailable response, 401 and RBAC 403 states preserve shell
      orientation and offer an appropriate retry/reset/back/reconnect/current-Web recovery without
      showing raw protocol text, credentials, absolute roots or private endpoints.
- [ ] FileIndex documents and query construction live in centralized typed entity/API/query
      boundaries. Feature components do not issue raw fetches, locally reinterpret backend authority,
      duplicate Bearer/RBAC handling or filter a server page as though it were a complete catalog.
- [ ] Unit, Python integration and built-artifact browser evidence prove that entry, search, filter,
      reset, paging, refresh and retry send bounded authenticated GETs only and create no Job, Task,
      Provider request, Reprocess/review action, audit mutation or Storage mutation.
- [ ] The catalog remains keyboard-usable and coherent at narrow and wide viewports; Task 32.1
      Storage Files, V1 `/ui`, Dashboard and other supported V2 routes remain regression-safe.
- [ ] The T3 commands below pass with actual results, and the checkpoint contains only this coherent
      Task plus its Developer Completion Report. Pre-existing/unrelated failures or unavailable gates
      are reported reproducibly rather than hidden, skipped or weakened.

## Required Tests

Run and report all of the following from the repository root:

```text
python3 scripts/check_governance.py
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e -- library-file-index.spec.ts
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_file_catalog tests.test_file_catalog_api tests.test_file_index_lifecycle tests.test_configuration_snapshot tests.test_v2_ui tests.test_release_security
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
git diff --check
```

Focused frontend tests must cover strict valid/malformed normalization, ignored unknown fields,
query encoding and draft/applied/reset behavior, deep-route auth continuation, Active selector
authority, catalog row semantics, all supported filter classes, equal-timestamp cursor boundaries,
next/previous context, empty/failure/recovery states, narrow/keyboard behavior, token secrecy and
zero non-GET/work requests. If the exact focused filename differs, run its replacement and report
the actual command.

Python tests must prove the new processing-disposition filter at application, in-memory/SQLite and
API levels, including invalid values, combination with other filters and stable pagination. Tests
use temporary databases and local fakes only; no production Storage, TMDB service, credentials,
private configuration or operator media may be accessed.

Full Python discovery and Docker release-security smoke remain Slice Final gates for this T3 Task;
their canonical commands are `.venv/bin/python -m unittest discover -s tests` and
`scripts/docker_release_security_smoke_test.py`. Report them as NOT RUN unless actual Task risk or a
new blocker requires escalation to T4; never imply PASS without execution.

## Non-goals

- FileIndex detail/explanation UI, occurrence/history expansion, related review/checkpoint views,
  Result relevance explanation, by-source resolution or physical/indexed detail links.
- Scan, Preview, Organize, Reprocess, re-recognize, re-match, re-plan, review/recovery,
  configuration editing/activation or any other state-changing action.
- Client-side filtering of a partial catalog, full-text search infrastructure, arbitrary query
  language, unbounded export, bulk selection/action or background indexing.
- Storage browsing changes, file content read/preview/download/upload, thumbnails/artwork,
  recursive Storage enumeration, media streaming or any Storage mutation.
- New endpoints, providers, schemas, identity/auth architecture, token persistence, SSR/BFF/Node
  production serving, V1 retirement, unrelated refactors or whole-Slice documentation reconciliation.

## Developer Completion Report

### Changed Files

- Backend authority and persistence: `mediaflow/domain/file_index.py`,
  `mediaflow/application/file_catalog.py`, `mediaflow/infrastructure/memory_file_index.py`,
  `mediaflow/infrastructure/sqlite_file_index.py`, and `mediaflow/interfaces/service_api.py`.
- Backend regression coverage: `tests/test_file_catalog.py` and `tests/test_file_catalog_api.py`.
- Typed frontend boundary: `web/src/entities/library/file-index-catalog.ts` and its tests,
  `web/src/features/library/file-index-query.ts`, `web/src/shared/api/api-client.ts`,
  `web/src/shared/api/api-errors.ts`, and `web/src/shared/api/library-api.test.ts`.
- V2 route and journey: `web/src/features/library/FileIndexCatalogPage.tsx` and its tests,
  `web/src/features/library/LibraryLanding.tsx`, `web/src/routes/router.tsx`,
  `web/src/shared/navigation/destination-model.ts` and its tests, plus shared styles.
- Browser proof and fixtures: `web/tests/e2e/library-file-index.spec.ts`,
  `web/tests/e2e/library-files.spec.ts`, and `web/tests/fake-server.mjs`.
- `TASK.md` — this Developer Completion Report and checkpoint state.

### Implemented

- Added the server-authoritative `processingDisposition` filter through the domain, application,
  in-memory/SQLite repositories and API, before paging, with validation, aliases, duplicate-query
  and cursor compatibility preserved.
- Built the real authenticated `/ui-v2/library/file-index` journey with Active-scope choices,
  submitted-versus-draft filters, reset, stable cursor paging and one-record lookahead.
- Corrected backward FileIndex paging so Memory/SQLite repositories select the nearest records
  before a cursor, the typed API trims the backward lookahead correctly, and cursor recovery clears
  only paging state while preserving submitted filters.
- Added strict allowlisted FileIndex normalization that rejects malformed documents, wrong-typed
  present canonical/nested facts and contradictory discovery/change/processing duplicates while
  ignoring unknown fields and excluding fingerprints, private paths and raw provider payloads.
- Rendered separate discovery/stability, current-occurrence, processing and identity facts with
  explicit unavailable states, bounded loading/empty/error/auth recovery and GET-only behavior.
- Added repository/API and focused frontend regressions, expanded secret-free fake-server fixtures,
  and built-artifact browser coverage for multi-page equal-timestamp paging, all filter classes,
  Active-without-ResourceLibrary, invalid/malformed/unavailable recovery, keyboard use and
  token/mutation absence.

### Tests and Results

From repository root:

```text
python3 scripts/check_governance.py                          PASS
npm --prefix web run format:check                            PASS
npm --prefix web run typecheck                               PASS
npm --prefix web run lint                                    PASS
npm --prefix web run test -- --run                           PASS (168 tests, 15 files)
npm --prefix web run build                                   PASS
npm --prefix web run test:e2e -- library-file-index.spec.ts  PASS (13 tests)
npm --prefix web run test:e2e                                PASS (47 tests)
.venv/bin/python -m unittest tests.test_file_catalog tests.test_file_catalog_api tests.test_file_index_lifecycle tests.test_configuration_snapshot tests.test_v2_ui tests.test_release_security PASS (90 tests)
.venv/bin/python -m unittest tests.test_file_catalog tests.test_file_catalog_api                PASS (18 tests, focused correction regressions)
.venv/bin/ruff format --check .                              PASS
.venv/bin/ruff check .                                       PASS
.venv/bin/python -m compileall -q mediaflow tests scripts  PASS
git diff --check                                             PASS
```

The frontend test run emitted non-failing jsdom `Window.scrollTo()` diagnostics. The specified
Python run emitted existing unclosed-database `ResourceWarning` messages but exited successfully;
the focused correction run had no failures. Full Python discovery and
`scripts/docker_release_security_smoke_test.py` were NOT RUN; they remain Slice Final gates for
this T3 Task.

### Decisions

- Kept the existing authenticated `/api/v1/file-index` authority and `/files` alias; the new
  processing filter is applied in the catalog query rather than in a partial client page.
- Kept applied filters in allowlisted route state while editing remains draft-only, so submit/reset
  and refresh/back preserve truthful query context without carrying credentials or authority.
- Used an optional bounded identity summary and explicit unavailable labels rather than inferring
  identity, current Result relevance or action eligibility from list facts.
- Preserved the existing stable `updatedAt` + `fileId` cursor contract by ordering backward
  repository reads ascending for bounded selection, reversing the selected records for the
  canonical descending response, and trimming the lookahead in the centralized API client.
- Treat duplicate canonical/nested facts as one consistency boundary: every present field is
  validated and two present representations must agree before a record is exposed.

### Remaining In-Slice Work

- FileIndex detail/explanation, occurrence/history, physical-to-index linkage, and current or
  historical Result explanation remain outside this Task's frozen boundary.
- Slice-level final review and validation evidence remain outside this Developer implementation
  checkpoint.

### Risks / Deviations

- Full Python discovery and Docker release-security smoke are intentionally NOT RUN under the T3
  scope; no external Storage, TMDB service, credentials or private configuration was used.
- Existing test-run warnings are recorded above; no test command failed.
- Pre-existing untracked `node_modules/` was preserved and not staged. Ignored `config/alist.json`
  was not staged; no credentials or private paths are in the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: e8a77fcae64bcda78fda46d29700e9794fdf9c7f
```

## B Review Result

```text
Reviewed: 4b1f8358199a6eaf00f043175c17eccedf0d7083..755ddf7b7232b97aad88487dd7a9c57bcf458f54
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Adjacent backward paging and cursor recovery do not preserve the promised bounded query context.
  `PageControls` sends `before` from the first item of the current page, while both repositories
  filter newer rows and take the first descending `limit`; a three-page probe produced page 1
  `['7', '6']`, page 2 `['5', '4']`, page 3 `['3', '2']`, then rendered `['7', '6']` for Previous
  instead of page 2. The existing browser fixture has only two pages, so its passing Previous test
  does not exercise this boundary. In addition, the invalid-cursor button labelled “Return to first
  page” calls the full filter reset and discards submitted filters. Correct the authoritative/UI
  paging behavior so Previous returns the immediately preceding page across three or more pages and
  equal timestamps, and make cursor recovery clear only paging state while explicit filter reset
  remains separate. Add repository/API and built-artifact regressions for both behaviors.
- The strict FileIndex normalizer does not fail the whole malformed document closed when canonical
  and nested duplicate facts are malformed or disagree. An in-memory execution of the actual
  TypeScript module accepted `scanStatus: 123` by falling back to `discovery.status: "ready"`, and
  accepted top-level `processingDisposition: "organized"` together with nested disposition
  `"failed"`. Validate any present canonical/nested field and reject wrong types or contradictory
  discovery/change/processing facts; add focused normalization regressions proving rejection.
- The mandatory focused frontend evidence is incomplete. The required Vitest and Playwright
  commands pass (164 unit tests and 6 focused/40 full browser tests), but inspection of
  `FileIndexCatalogPage.test.tsx` and `library-file-index.spec.ts` finds no FileIndex viewport or
  keyboard interaction, no Active-with-no-ResourceLibrary state, no invalid-filter or
  malformed/unavailable FileIndex UI recovery, and no submitted UI exercise of the remaining
  ResourceLibrary/Storage/discovery/identity filter classes. Add only the Task-required focused
  coverage for these states and controls, including the multi-page equal-timestamp boundary above;
  rerun the original T3 gate.
