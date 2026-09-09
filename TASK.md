# Task 32.1 — V2 Active Storage Files journey

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 32.1
Parent Slice: 32
Status: READY FOR B REVIEW
Task Base: 12568825cadcd587db6363aa1db612ca3efcfdb2
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Complete the first independently usable Slice 32 journey: an authenticated operator can enter the
real V2 Library surface, choose an available configured Active Storage without typing its ID, browse
bounded immediate directories/files with Storage-relative navigation and FileIndex membership, and
recover safely from read failures without starting work or mutating state. This directly advances
RO-1, completes the Storage-files behavior in RO-2, and advances RO-6 through RO-8.

## Why This Task Exists

At Task Base, `/ui-v2/library` is still a generic migration page. The existing Python application
already exposes authenticated read-only authority through `GET /api/v1/system/status` and
`GET /api/v1/storage/files`, including exact managed-runtime identity, bounded Storage-relative
entries, breadcrumbs, cursors, provider-safe failures and FileIndex membership. The V1 UI consumes
those contracts, but V2 has no typed model, query, route or user journey for them.

This is the largest reasonable first unit because Library entry, Active Storage discovery, API
normalization, routing, browsing, visible state, failure recovery and browser proof must work
together to be independently useful. FileIndex search/list and rich detail are separate coherent
journeys with materially different models and remain for later Tasks in this Slice; splitting the
route, model or one response field into smaller Tasks would not produce an acceptable user outcome.

## Implementation Scope

The implementation boundary is:

```text
Existing Active runtime/System status + Storage read application behavior
→ existing authenticated API projections
→ typed V2 entities/API/query boundary
→ Library landing and Storage Files routes/views
→ unit/component/router/browser and affected Python regression tests
```

- Replace the `/library` migration placeholder with a real Library landing that plainly separates
  **Storage files** from **FileIndex**. Storage files opens the implemented V2 journey; FileIndex
  remains an honest current-Web continuation until its later Slice 32 Task and is not a dead or
  falsely implemented control.
- Add a supported refresh-safe Storage Files child route under `/library`. Compose it with the Slice
  31 shell, title/active-route metadata, memory-only authentication continuation and safe allowlisted
  view state. Storage-relative path and opaque paging cursor may enter route/search state only when
  safely encoded; no token, credential, root path or execution authority may enter a URL.
- Extend the centralized typed frontend API boundary with strict normalization for:
  - the minimum allowlisted `system/status` fields needed to identify a managed Active snapshot and
    present selectable configured Storages/related enabled ResourceLibraries; and
  - the runtime Files document: configuration identity, Storage-relative path/breadcrumbs, bounded
    entries, entry type/size/modified time, pagination/exhaustion, side-effect statement and bounded
    FileIndex membership.
- Add the Storage display name to the existing allowlisted Python System Status Storage projection
  if needed for an operator-meaningful selector. Preserve the existing response and authority
  semantics, expose no Storage root/options/credentials, and cover the projection with its affected
  Python tests. Do not add a new endpoint or alternate configuration authority.
- Build feature-owned TanStack Query options and UI state so the operator can select from the exact
  backend-reported managed Active Storages, open the root, traverse immediate directories and
  breadcrumbs, move through a bounded next page and return to a prior page/context, refresh the
  current read, and switch Storage without retaining an invalid path/cursor.
- Render operator-meaningful loading, no-Active/no-Storage, empty-directory and success states.
  Each file row exposes only safe read facts and truthfully distinguishes indexed, not indexed,
  unavailable and truncated/ambiguous membership; this Task does not infer processing state from
  membership or create the later V2 FileIndex detail route.
- Map authentication rejection, RBAC denial and Files-specific invalid path/cursor, missing library,
  managed-configuration unavailable and provider read/permission failures to bounded, secret-free
  states with a concrete retry, breadcrumb/landing return, Storage reselection, reconnect or current
  V1 Configuration continuation as appropriate. Do not collapse a Storage-provider permission
  failure into a claim that the API principal lacks RBAC permission; distinguish them from stable
  response code/category, never raw provider text.
- Keep every request in this journey an explicit bounded `GET`. Query prefetch, render, refresh,
  selection, navigation and retry must not invoke Scan, Preview, Organize, Reprocess, Provider work,
  Task/Job admission, audit writes or any Storage mutation.
- Add responsive and keyboard-usable presentation using the existing shared UI foundation. Preserve
  V1 `/ui`, Dashboard and the Operations/Review/Configuration migration surfaces.
- Extend the local Playwright fake with only secret-free System Status and runtime Files GET
  fixtures/failures needed for this journey; it must continue rejecting unsupported mutation
  methods and must never log Bearer values.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, stable requirements and all A-owned Contract fields.
- FileIndex search/list/detail implementation, cross-surface detail navigation, operational action
  submission and review/recovery behavior; these remain later work inside the Slice or Explicitly
  Deferred as stated by the Contract.
- Existing Storage/domain/persistence behavior, Active activation lifecycle, RBAC permissions,
  mutation endpoints and OrganizerExecutor boundaries except for the narrow allowlisted System
  Status display-name projection above.

## Acceptance Criteria

- [ ] `/ui-v2/library` is a real shell-integrated Library landing, visually and semantically
      distinguishes Storage files from FileIndex, opens the implemented Storage Files route, and
      offers a truthful current V1 Web continuation for FileIndex without a false V2 claim.
- [ ] Direct or refreshed unauthenticated entry to the Storage Files route returns through the
      existing memory-only connection boundary to the intended safe route; connect/disconnect and
      401 cache clearing retain the Slice 31 behavior and never persist or expose the token.
- [ ] With a valid managed Active runtime, the operator chooses a backend-reported Storage using an
      operator-meaningful label, reaches its root without typing an ID, and sees only allowlisted
      Active identity plus Storage-relative browse state. Draft/JSON/local rows are not presented as
      managed Active authority.
- [ ] The operator can open an immediate directory, use breadcrumbs, request a bounded next page,
      return to a prior page/context, refresh, and switch Storage. Path/cursor state stays scoped to
      the selected Storage and no frontend code invents cursors, recursively enumerates Storage or
      exposes an absolute/provider root.
- [ ] Directory and file entries render bounded safe facts; membership accurately distinguishes
      indexed, not indexed, unavailable and truncated/ambiguous cases without inventing a processing
      disposition or linking to a not-yet-implemented V2 detail page.
- [ ] Loading, empty directory, no managed Active runtime, no available Storage, malformed response,
      invalid/escaped path, invalid/stale cursor, missing ResourceLibrary, provider read/permission
      failure, 401 and RBAC 403 states remain in shell context and provide the smallest valid
      retry/back/reselect/reconnect/current-Web recovery. Raw API/provider text and private paths are
      not rendered.
- [ ] System Status and Files data are validated in centralized typed entity/API/query boundaries;
      feature components do not issue raw fetches, duplicate Bearer/RBAC handling, infer backend
      authority or trust unknown response fields.
- [ ] All Library landing and Storage Files traffic is bounded authenticated GET traffic. Unit and
      browser evidence proves view/navigation/refresh/retry creates no Job, Task, Provider request,
      Reprocess/review action, audit write or Storage mutation and sends no non-GET API request.
- [ ] The journey is keyboard-usable and coherent at narrow and wide viewports, with useful focus,
      headings, labels and active-route/title behavior; existing V1 `/ui`, Dashboard and remaining
      migration routes continue to work.
- [ ] The T3 test commands below pass with actual results, and the checkpoint contains only this
      coherent Task plus its Developer Completion Report. Any pre-existing/unrelated failure is
      reported with reproducible evidence rather than hidden or weakened.

## Required Tests

Run and report all of the following from the repository root:

```text
python3 scripts/check_governance.py
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e -- library-files.spec.ts
.venv/bin/python -m unittest tests.test_configuration_snapshot tests.test_runtime_files_browser tests.test_v2_ui tests.test_release_security
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests
git diff --check
```

Focused frontend tests must include strict valid/malformed normalization, ignored unknown fields,
query URL encoding/scoping, Library landing truthfulness, direct/deep route auth continuation,
Storage selection, root/directory/breadcrumb/page-back/switch/refresh behavior, membership variants,
all Acceptance Criteria failure/recovery categories, narrow/keyboard use, token secrecy and zero
non-GET/work requests. If the exact test filename differs, run the focused replacement plus the full
Playwright suite selector needed to prove the same journey and report the actual command.

Python tests use temporary Storage roots and local fakes only. No production Local/SMB/OpenList/S3/
TMDB service, credentials, private configuration or operator media may be accessed. Full Python
unittest discovery and Docker smoke are reserved for Slice Final unless an implementation change
raises the Task to T4 risk.

## Non-goals

- FileIndex search/filter/list, FileIndex detail/explanation and V2 physical-to-indexed detail
  navigation beyond truthful membership display; these are later coherent Tasks in Slice 32.
- Scan, Preview, Organize, Reprocess, re-recognize, re-match, re-plan, review, checkpoint, recovery,
  configuration editing/activation or any other POST/PUT/PATCH/DELETE action.
- File selection for work, file content read/preview/download/upload, thumbnails/artwork, recursive
  tree loading, media streaming, arbitrary host browsing or Storage mutation.
- New API endpoints, Storage providers, adapters, schemas/repositories, FileIndex lifecycle behavior,
  full-text search, domain redesign or changes to V1 execution/authorization behavior.
- V1 UI retirement, identity redesign, token persistence, SSR/BFF/Node production serving, unrelated
  refactors, optional polish or closure reconciliation for the whole Slice.

## Developer Completion Report

### Changed Files

- `mediaflow/infrastructure/configuration_snapshot.py` — add the Storage display name to the
  allowlisted System Status Storage projection; no root/options/credentials added.
- `tests/test_configuration_status.py` — Python regression proving the operator name is exposed and
  the private root is not.
- New typed V2 entities/guards: `web/src/entities/shared/normalize.ts`,
  `web/src/entities/library/system-status.{ts,test.ts}`,
  `web/src/entities/library/storage-files.{ts,test.ts}`.
- Centralized API/query boundary: `web/src/shared/api/api-client.ts`, `api-errors.ts`,
  `library-api.test.ts`, `web/src/features/library/system-status-query.ts`,
  `storage-files-query.ts`.
- Feature/route surface: `web/src/features/library/LibraryLanding.tsx`,
  `StorageFilesPage.tsx`, `web/src/routes/router.tsx`, shared UI styles.
- Auth/navigation continuation for refresh-safe Storage Files query state:
  `api/auth-store.ts`, `api/auth-context.ts`, `shared/auth/AuthBoundary.tsx`,
  `shared/navigation/destination-model.ts`, `features/entry/EntryPage.tsx` plus focused tests.
- Browser proof/fakes: `web/tests/e2e/library-files.spec.ts`, `web/tests/fake-server.mjs`, and
  updated Dashboard/deep-link specs for the real Library landing.
- `TASK.md` — this Developer Completion Report and checkpoint state.

### Implemented

- `/ui-v2/library` is now a real shell-integrated Library landing that clearly separates Storage
  files (implemented V2 journey) from FileIndex (truthful current-Web continuation).
- A refresh-safe Storage Files route lets the operator choose a backend-reported Active Storage by
  its operator label, browse root/immediate directories with breadcrumbs, request the bounded next
  page, refresh, return to Library, and switch Storage without carrying stale path/cursor state.
- Strict frontend normalization covers the allowlisted System Status and runtime Files documents;
  unknown fields are ignored and shape violations become one bounded malformed read state.
- Files provider/permission/configuration failures are bounded results, so a Storage-provider 403
  never clears a valid API principal; RBAC 403 and 401 still use the shared authority lifecycle.
- Deep-link continuation now retains only allowlisted Storage Files view state (`storage`, `path`,
  `cursor`) through the memory-only connection boundary; 401 rejection preserves the active route
  for explicit re-entry.
- Loading, no-Active, no-Storage, empty, malformed, invalid-path, not-found, provider, 401 and 403
  states render bounded operator language with retry/back/reselect/reconnect/V1 continuation.

### Tests and Results

From repository root:

```text
python3 scripts/check_governance.py                          PASS
npm --prefix web run format:check                            PASS
npm --prefix web run typecheck                               PASS
npm --prefix web run lint                                    PASS
npm --prefix web run test -- --run                           122 passed
npm --prefix web run build                                   PASS
npm --prefix web run test:e2e -- library-files.spec.ts       11 passed
npm --prefix web run test:e2e                                27 passed
.venv/bin/python -m unittest tests.test_configuration_status PASS
.venv/bin/python -m unittest tests.test_configuration_snapshot tests.test_runtime_files_browser tests.test_v2_ui tests.test_release_security PASS
.venv/bin/ruff format --check .                              PASS
.venv/bin/ruff check .                                       PASS
.venv/bin/python -m compileall -q mediaflow tests scripts PASS
git diff --check                                             PASS
scripts/docker_release_security_smoke_test.py                NOT RUN (T3 scope; reserved for Slice Final per Task)
.venv/bin/python -m unittest discover -s tests               NOT RUN (T3 scope; full regression reserved for Slice Final per Task)
```

Browser evidence covers landing truthfulness, direct/deep auth continuation with allowlisted query
state, Storage selection, root/directory/breadcrumb/page/refresh/switch, membership variants,
no-Storage, provider failure, invalid path/not-found, 401/403, malformed retry, narrow keyboard use,
token secrecy and zero non-GET requests.

### Decisions

- Kept the Storage Files route under the `/library/files` URL and centralized route metadata, using
  the existing flat route tree with an allowlisted child destination model for titles and auth
  continuation.
- Files identity (`authority`/`revisionId`) is read from the runtime document `configuration`
  block, matching the actual backend projection.
- Files 5xx provider/configuration failures with a known bounded envelope are returned as
  `StorageFilesRead` results instead of shared errors so a provider denial never impersonates an
  API-principal denial; only real 401/RBAC 403 travel through the shared boundary.
- The Files query is gated on the successful System Status read and nested under the shared
  authorized-read boundary so both endpoints share the same cache/auth lifecycle without racing.
- Only `storage`, `path` and `cursor` query state is retained across an unauthenticated deep-entry
  reconnect; arbitrary search text and token-like material are never carried.

### Remaining In-Slice Work

- FileIndex list/search/filter and detail/explanation journeys (later Slice 32 Tasks).
- Cross-surface physical-to-indexed detail navigation beyond the membership display implemented
  here, plus Slice-level responsive/accessibility and final validation evidence.

### Risks / Deviations

- No known failures. Full Python unittest discovery and the Docker release-security smoke test are
  intentionally not run under this T3 Task; both remain Slice Final gates and are documented above
  rather than inferred.
- The Playwright fake only mirrors secret-free System Status/Files GET fixtures; real SMB/OpenList/
  S3/TMDB services and credentials are never used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: e955eef3d6045e365957d32e269c5110f2c0eca4
```

## B Review Result

```text
Reviewed: 12568825cadcd587db6363aa1db612ca3efcfdb2..e955eef3d6045e365957d32e269c5110f2c0eca41aaf95d2df53817fa94a977a8f8d
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
