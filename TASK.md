# Task 32.3 — V2 FileIndex detail and physical/indexed context

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 32.3
Parent Slice: 32
Status: FIX REQUIRED
Task Base: 3e556026cf432571a6c434e07b0cfd59ab29e22a
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Complete the remaining V2 Library read journey: an authenticated operator can open a refresh-safe
FileIndex detail, understand the bounded current and historical evidence MediaFlow actually has,
move safely between a uniquely linked physical Storage file and its indexed record, and recover
from absent or uncertain linkage without starting work. This completes RO-4 and RO-5 and closes the
remaining detail/linkage portions of RO-1 and RO-6 through RO-8.

## Why This Task Exists

Tasks 32.1 and 32.2 delivered the real V2 Library landing, Active Storage browser and FileIndex
catalog. The catalog still has no detail destination, while Storage membership is reduced to a
label even when the backend has one unique FileIndex match. The authoritative Python surface already
provides rich redacted detail at `GET /api/v1/files/{fileId}`, source resolution at
`GET /api/v1/files/by-source`, and bounded membership in the Active Storage response, but V2 has no
typed detail/by-source model or composed navigation.

Detail explanation and physical/indexed navigation are one operator journey: the link is useful
only if the destination explains the record, and the explanation must retain a safe path back to
the physical/list context. Implementing these together is the largest remaining independently
reviewable Slice unit; operational, review/recovery and configuration mutations remain assigned to
later Slices.

## Implementation Scope

The implementation boundary is:

```text
existing FileCatalog detail/by-source and Active Storage membership authority
→ minimal backward-compatible read projection where required
→ strict typed V2 detail/link entities and query options
→ FileIndex detail route plus catalog/Storage navigation
→ unit, Python integration and built-artifact browser regressions
```

- Add a shell-integrated, refresh-safe detail route at `/library/file-index/$fileId`, including
  centralized route title/active-navigation metadata and Slice 31 memory-only auth continuation.
  Catalog entries open this route and preserve a safe return to the submitted FileIndex query.
- Add strict centralized normalization for the bounded detail document. Model only the
  operator-facing facts required by the Slice: Storage-relative source and ResourceLibrary identity;
  discovery, stability and current/legacy occurrence state; bounded fingerprint provenance/state
  without displaying the fingerprint value; parser, recognition, metadata, naming, classification,
  target and processing evidence when present; current versus historical TaskItem/Result relevance;
  related review/checkpoint summaries; failure/outcome/next-action explanation; and per-section
  truncation or availability.
- Treat the backend projection as authoritative. Validate every present modeled field, ignore
  unknown fields, reject contradictory or malformed documents as a whole, and do not infer a
  current Result, successful effect, safe retry, recognition decision, target or available action
  from path/File ID/history alone. Never render raw provider payloads, raw exceptions, absolute
  roots, fingerprint values, source-fingerprint values, credentials or private endpoints.
- Add feature-owned authenticated GET/query options for detail and by-source resolution through the
  shared API client. Preserve existing RBAC, 401 handling and cache clearing; feature components must
  not issue raw fetches or duplicate protocol/error policy. A minimal backward-compatible safe enum
  or bounded field may be added to by-source/detail output if the existing prose-only projection
  cannot distinguish missing from ambiguous linkage without client-side string interpretation.
- Extend the Storage Files entity/view so a file offers an indexed destination only after an
  explicit bounded by-source read confirms one current unique match. Scope resolution by the Active
  Storage and ResourceLibrary when available. Missing, ambiguous, truncated and unavailable
  membership/resolution remain distinct, do not select an arbitrary record, and offer only an honest
  refresh, scoped FileIndex catalog or current V1 continuation.
- From detail, provide a safe route back to the originating catalog query and, when the source can
  be represented by an Active Storage-relative parent context, to the relevant Storage Files
  directory. Direct entry without return state still has stable Library/FileIndex parent recovery.
  Route state may contain only bounded allowlisted view context; no token, fingerprint, occurrence
  authority, private root or backend action URL may enter it.
- Group the detail in operator language so discovery/stability, current occurrence, processing,
  identity/policy explanation, target/outcome, history/relevance and related recovery state remain
  visibly distinct. Empty or legacy evidence is labelled unavailable/unverified rather than
  reconstructed. Truncated sections say that more exists without recursively loading it.
- Show non-migrated Scan, Preview, Organize, Reprocess, review/recovery and configuration next steps
  only as explanatory unavailable state or an explicit current V1 Web continuation. Do not render
  backend `currentActions` or resolution identifiers as executable V2 controls, and do not transfer
  the Bearer token or promise a V1 deep link that is not supported.
- Keep loading, stale/deleted/not-found detail, missing/ambiguous/truncated source linkage,
  malformed/unavailable detail or resolver response, no Active physical context, 401 and RBAC 403
  states inside the shell with the smallest truthful retry/back/catalog/reconnect/current-Web
  recovery. Preserve useful prior context where safe.
- Keep catalog, detail, resolver and Storage navigation strictly read-only. No prefetch or retry may
  call Storage content, Providers, POST/PUT/PATCH/DELETE, Scan, Preview, Organize, Reprocess, review
  continuation, authorization/grant, audit mutation or OrganizerExecutor.
- Add responsive and keyboard-usable presentation using the existing V2 shell and design-system
  primitives. Preserve Task 32.1 Storage browsing, Task 32.2 filtering/paging, Dashboard, V1 `/ui`,
  API compatibility and Python-served production assets.
- Extend the Playwright fake only with bounded secret-free detail/by-source GET fixtures and failure
  modes. It must reject unsupported methods and never log or persist Bearer values, fingerprints or
  private paths.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, canonical/stable requirement text and all A-owned Contract fields.
- Scan/Preview/Organize/Reprocess, review/recovery, configuration editing/activation and every other
  operational mutation assigned to Slices 33–35.
- FileIndex schema/lifecycle redesign, unbounded history/export, Provider calls, Storage content
  reads, physical-file mutation and V1 behavior beyond a minimal compatible read projection.

## Acceptance Criteria

- [ ] `/ui-v2/library/file-index/$fileId` is a real typed route with correct shell title/active
      navigation across catalog entry, direct entry, refresh and memory-only auth continuation.
      Catalog → detail → back restores the useful submitted query/page context without credentials
      or mutation authority in the URL.
- [ ] A valid detail groups bounded source/library, discovery/stability, occurrence/fingerprint
      state, processing, parser/recognition/metadata/policy/target evidence, Result outcome/relevance,
      related review/checkpoint state and next-destination explanation when those facts exist.
      Current, historical, legacy and unavailable facts are not conflated or guessed.
- [ ] Detail normalization is centralized, allowlisted and strict. Malformed/contradictory modeled
      data fails the whole document closed; unknown fields are ignored; raw fingerprints, source
      fingerprints, credentials, provider payloads, absolute roots, private endpoints and raw
      exception text never enter the typed model, route, DOM, logs or captured browser artifacts.
- [ ] A physical Storage file can resolve and open exactly one current FileIndex record through the
      authoritative membership/by-source boundary. Missing, ambiguous, truncated or unavailable
      linkage never navigates to an arbitrary record and has a truthful read-only recovery.
- [ ] Detail can return to the originating FileIndex query and can open the relevant Active
      Storage-relative parent context when safely expressible. Stale/deleted records, missing Active
      Storage or an unsafe/unavailable physical context fall back to a valid Library/FileIndex
      parent instead of fabricating a host path or Active membership.
- [ ] Loading, empty/absent evidence, truncated history, not-found/stale detail, malformed or
      unavailable detail/resolver, 401 and RBAC 403 states stay oriented in the shell and offer a
      concrete retry/back/catalog/reconnect/current-Web continuation without protocol leakage.
- [ ] Operational and configuration actions remain explanatory or use an explicit current V1 Web
      handoff only. No V2 Library control submits Scan, Preview, Organize, Reprocess, review,
      recovery or configuration work, and no backend action token/identifier is presented as
      ordinary operator ceremony.
- [ ] Detail and linkage documents/query construction live in centralized typed entity/API/query
      boundaries. Feature components do not issue raw fetches, reinterpret backend relevance/RBAC/
      Active authority, inspect server prose to make business decisions or create a parallel API.
- [ ] Unit, Python integration and built-artifact browser evidence proves list/detail/by-source/
      physical navigation uses bounded authenticated GETs only, preserves useful context, creates no
      Job/Task/Provider/audit/work request or Storage mutation, and keeps secrets/private paths out
      of routes, persistent browser stores, console output and artifacts.
- [ ] The journey is keyboard-usable and coherent at narrow and wide viewports; Task 32.1 Storage
      browsing, Task 32.2 catalog filters/paging, V1 `/ui`, Dashboard and supported V2 routes remain
      regression-safe.
- [ ] The T3 commands below pass with actual results, and the checkpoint contains only this coherent
      Task plus its Developer Completion Report. Pre-existing/unrelated failures and unavailable
      gates are reported reproducibly rather than hidden, skipped or weakened.

## Required Tests

Run and report all of the following from the repository root:

```text
python3 scripts/check_governance.py
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e -- library-file-detail.spec.ts
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_file_media_detail tests.test_file_catalog tests.test_file_catalog_api tests.test_storage_browser tests.test_file_index_lifecycle tests.test_v2_ui tests.test_release_security
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
git diff --check
```

Focused frontend tests must cover strict valid/malformed detail and by-source normalization; ignored
unknown/sensitive fields; catalog and unique physical-file entry; refresh/deep-link auth; list and
physical return context; current/historical/legacy/missing/truncated rendering; not-found,
ambiguous, unavailable, malformed, 401 and 403 recovery; honest V1 handoff; narrow/wide keyboard
use; and absence of non-GET/work requests, token persistence and fingerprint/private-path output. If
the exact focused filename differs, run its replacement and report the actual command.

Python tests must preserve and prove bounded detail/by-source/membership behavior, missing and
ambiguous resolution, RBAC, redaction, source/result relevance, truncation, Active Storage
confinement and GET-only side effects. Tests use temporary databases and local fakes only; no
production Storage, Provider, credentials, private configuration or operator media may be accessed.

Full Python discovery (`.venv/bin/python -m unittest discover -s tests`), `npm --prefix web ci` and
Docker release-security smoke remain Slice Final gates for this T3 Task. Report them as NOT RUN
unless actual Task risk or a newly discovered blocker requires escalation; never imply PASS without
execution.

The Docker release-security smoke command is `python3 scripts/docker_release_security_smoke_test.py`.

## Non-goals

- Any state-changing Scan, Preview, Organize, Reprocess, review/recovery, configuration or execution
  control in V2; those journeys remain assigned to Slices 33–35.
- File upload/download/content preview, media streaming, artwork, recursive Storage loading,
  arbitrary filesystem access, file edit/rename/delete or any Storage mutation.
- Unbounded history, background refresh/prefetch, new FileIndex lifecycle/schema, full-text search,
  Provider access during reads or frontend reconstruction of missing pipeline decisions.
- Auth redesign, token persistence, SSR/BFF/Node production serving, V1 retirement, Slice-level
  documentation reconciliation, unrelated refactors or optional P2/P3 polish.

## Developer Completion Report

### Changed Files

- `mediaflow/interfaces/service_api.py` and `tests/test_file_media_detail.py` — bounded by-source
  reason projection and regression assertions.
- `web/src/entities/library/file-detail.ts`, `file-detail.test.ts`, `file-index-catalog.ts`,
  `storage-files.ts` and `storage-files.test.ts` — strict detail/linkage/membership models and
  normalization tests.
- `web/src/shared/api/api-client.ts`, `web/src/features/library/file-detail-query.ts`,
  `file-index-query.ts` and `file-index-query.test.ts` — authenticated typed GET/query boundaries
  and bounded return context.
- `web/src/features/library/FileIndexCatalogPage.tsx`, `FileIndexDetailPage.tsx`,
  `StorageFilesPage.tsx`, `web/src/routes/router.tsx` — detail route and catalog/Storage journey.
- `web/src/shared/auth/AuthBoundary.tsx`, `web/src/shared/navigation/destination-model.ts` and
  its tests, `web/src/shared/ui/AppShell.tsx` — dynamic route metadata and safe continuation.
- `web/tests/e2e/library-file-detail.spec.ts`, `library-files.spec.ts` and `fake-server.mjs` —
  built-artifact browser fixtures and read-only journey coverage.
- `TASK.md` — this Developer Completion Report and checkpoint state.

### Implemented

- Added the authenticated, refresh-safe `/ui-v2/library/file-index/$fileId` route with shell title,
  active navigation, catalog return context and memory-only auth continuation.
- Added centralized strict normalization for bounded FileIndex detail and by-source documents. It
  validates modeled facts, rejects malformed/contradictory relevance, ignores unknown fields and
  retains only explicitly allowlisted, bounded pipeline facts and checkpoint explanations; raw
  fingerprints, provider payloads, private paths and exception values never enter the model.
- Rendered distinct source/library, discovery/stability, occurrence, processing, identity/policy,
  parser/recognition/metadata/naming/classification/plan/operation evidence, Result relevance,
  TaskItem checkpoint, review, reprocess explanation and recovery sections.
- Corrected the detail correction loop by preserving safe evidence values/items/warnings and
  unavailable reasons, rendering durable checkpoint facts, using the authoritative `reviews`
  truncation key, and requiring a matching enabled Active ResourceLibrary-to-Storage binding
  before offering physical navigation.
- Added an explicit authoritative by-source GET after operator intent. Only one confirmed current
  match can open a FileIndex detail; missing, ambiguous, truncated, malformed and unavailable
  linkage remain non-navigating bounded states.
- Added safe physical Storage parent navigation, allowlisted `q_` catalog return state, dynamic
  route recognition and bounded 401/403/not-found/unavailable recovery.
- Preserved GET-only behavior and V2 read-only boundaries; no V2 work or configuration control was
  added. Extended secret-free fake-server and Python/frontend regression coverage.

### Tests and Results

From repository root:

```text
python3 scripts/check_governance.py                          PASS
npm --prefix web run format:check                            PASS
npm --prefix web run typecheck                               PASS
npm --prefix web run lint                                    PASS
npm --prefix web run test -- --run                           PASS (191 tests, 17 files)
npm --prefix web run build                                   PASS
npm --prefix web run test:e2e -- library-file-detail.spec.ts PASS (7 tests)
npm --prefix web run test:e2e                                PASS (54 tests)
npm --prefix web run test -- --run src/entities/library/file-detail.test.ts PASS (17 tests)
.venv/bin/python -m unittest tests.test_file_media_detail tests.test_file_catalog tests.test_file_catalog_api tests.test_storage_browser tests.test_file_index_lifecycle tests.test_v2_ui tests.test_release_security PASS (76 tests)
.venv/bin/ruff format --check .                              PASS (301 files)
.venv/bin/ruff check .                                       PASS
.venv/bin/python -m compileall -q mediaflow tests scripts  PASS
git diff --check                                             PASS
```

The Vitest run emitted existing non-failing jsdom `Window.scrollTo()` diagnostics. The specified
Python run emitted existing unclosed-database `ResourceWarning` messages but exited successfully.
Full Python discovery (`.venv/bin/python -m unittest discover -s tests`), `npm --prefix web ci` and
Docker release-security smoke (`python3 scripts/docker_release_security_smoke_test.py`) were NOT
RUN; the Task defines them as Slice Final gates. No external Storage, Provider, credentials or
private configuration was used.

### Decisions

- Kept existing FileCatalog detail/by-source and Active Storage authorities. Added only the
  secret-free `reason` enum needed to distinguish missing from ambiguous linkage without parsing
  backend prose.
- Kept physical-to-index navigation behind explicit operator intent and an authoritative resolver;
  bounded Storage membership is only a hint and never selects a record by itself.
- Kept detail evidence and checkpoint rendering behind centralized allowlists with bounded text,
  identifier and relative-path validation; unknown provider/payload/error fields are discarded and
  known unsafe explanations are redacted or mapped to a safe unavailable label.
- Used allowlisted bounded route context and the existing memory-only auth store. No token,
  fingerprint, occurrence authority or backend action URL enters navigation state.
- Kept operational, review/recovery and configuration controls explanatory or handed off to the
  current Web UI; all new Library reads use shared authenticated GET/query boundaries.

### Remaining In-Slice Work

- Slice 32-level final validation and review remain outside this Developer checkpoint; operational,
  review/recovery and configuration journeys explicitly deferred by the Slice Contract remain
  deferred.

### Risks / Deviations

- Full Python discovery, `npm --prefix web ci` and Docker release-security smoke were intentionally
  not run because the Task assigns them to Slice Final. They are not reported as PASS.
- Pre-existing untracked `node_modules/` was preserved and not staged. Ignored `config/alist.json`
  was not staged; no credentials, private paths or binary artifacts are in the Task files.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: ad8ba3b272e683ab2bb1627b4df8f60aa49d6e99
```

## B Review Result

```text
Reviewed: 3e556026cf432571a6c434e07b0cfd59ab29e22a..94583c7c16dfe93b12f4602f3d576f2c8570bdcb
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The valid detail does not expose the bounded pipeline/checkpoint facts required by the Task when
  they exist. `normalizeEvidenceSection()` reduces each redacted section to item/warning counts and
  discards its allowlisted `value`, `items`, warnings and unavailable explanation; TaskItem
  checkpoints are likewise reduced to an availability boolean. The browser therefore renders only
  count/availability labels instead of the parser, recognition, metadata, naming, classification,
  plan/target and checkpoint explanation promised by the Goal and second Acceptance Criterion.
  Preserve and render bounded, explicitly allowlisted, secret-free operator facts from these
  authoritative summaries without rendering raw payloads or exceptions, and cover their valid and
  unavailable forms.
- Truncation and legacy detail behavior do not satisfy the required rendering proof. The backend
  emits `truncated.reviews` and the normalizer retains that key, but the page checks
  `truncated.relatedReviews`, so review truncation is never shown. In addition,
  `library-file-detail.spec.ts` has no legacy-detail fixture/assertion and its detail fixture sets
  the top-level truncation flags false; the independently rerun focused suite still passes all 6
  tests without exercising the Task-required current/historical/legacy/missing/truncated rendering.
  Correct the review key and add focused fixtures/assertions that prove legacy/unavailable evidence
  and each relevant bounded truncation state remain distinct and oriented.
- The detail-to-physical link validates only that `record.storageId` exists in Active status. It
  does not require an enabled Active ResourceLibrary whose id and Storage binding match the detail
  record, yet it passes `record.resourceLibraryId` to `/library/files`. This can fabricate a
  physical-context destination for a stale/disabled/mismatched ResourceLibrary instead of using the
  required Library/FileIndex fallback. Gate the link on the matching enabled Active
  ResourceLibrary-to-Storage binding and add focused coverage for the unavailable/mismatched Active
  physical-context case.
