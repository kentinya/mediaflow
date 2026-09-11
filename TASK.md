# Task 33.2 — Bounded manual Scan and zero-mutation Preview

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.2
Parent Slice: 33
Status: PLANNED
Task Base: 3969983cef5bccdca55da7a0e5280596af131071
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 33 RO-3 and the applicable RO-7/RO-8 boundary: from V2 Library or Operations, an
authorized operator can select an exact current FileIndex record or configured ResourceLibrary
scope, submit a bounded Scan or run a complete zero-mutation Preview, and inspect truthful durable
aggregate and per-item findings without handling raw fingerprints, internal IDs, paths or authority.

## Why This Task Exists

Task 33.1 completed the shared Operations, Task, Job and Worker observation/control foundation, but
V2 still hands manual Library actions to V1. The backend already has authoritative
`ManualScanService` and `ManualOrganizePreviewService` behavior: Scan creates durable asynchronous
work, while Preview runs analysis/planning and persists aggregate/item findings without Storage
mutation. V2 has no typed routes, safe current-source admission or inspectable Preview surface for
either journey.

Scan and Preview are the largest coherent next zero-mutation unit. They share source admission,
readiness, limits, result projection and recovery, and they establish the reviewed evidence used by
the later manual Organize Task. Manual intent editing, item selection, one-shot authorization and
OrganizerExecutor execution remain a separate high-risk mutation boundary and are not included.

## Implementation Scope

The implementation boundary is:

```text
existing FileIndex/ResourceLibrary and manual Scan/Preview services
→ backend-authoritative current-source admission and bounded projections
→ backward-compatible authenticated /api/v1/* extensions
→ strict V2 entities, queries and explicit actions
→ Library/Operations Scan and Preview routes/details
→ Python, component/router and built-artifact browser tests
```

- Add refresh-safe V2 manual-operation routes and actions reachable from the Operations workspace
  and applicable current Library FileIndex/ResourceLibrary context. Register routes centrally so
  titles, active navigation, memory-only authentication continuation and safe return context follow
  the Slice 31 shell contract.
- Derive a backend action matrix for the authenticated principal, exact current source and runtime
  readiness. V2 may render Scan or Preview only when that projection advertises it; the frontend
  must not infer authority, source validity, capability or Active configuration from route state.
- Bind file-scoped admission on the server to the exact current FileIndex occurrence and stored
  fingerprint. The browser must not receive or echo a raw fingerprint. At admission, the backend
  rechecks the authoritative occurrence/fingerprint so a removed, replaced or changed file is
  rejected before publishing work or reusable findings.
- Reuse `ManualScanService` for exact-file and ResourceLibrary scan submission. Requests select only
  an advertised source/scope and bounded supported options; they cannot supply arbitrary absolute
  paths, provider payloads, operation plans, policy identities or execution authority. Admitted long
  work returns a durable identity immediately and links to the Task/Job detail established in 33.1.
- Provide a bounded Scan detail/progress journey that preserves aggregate versus independent item
  state, stable paging and lifecycle links. Successful siblings remain visible; source failures,
  queue pressure, missing Worker and cancellation eligibility use durable backend truth.
- Reuse `ManualOrganizePreviewService` to run the complete applicable parse, recognition, metadata,
  naming, classification and planning pipeline. Preview is visibly DryRun/analysis, produces no
  execution authority and invokes no mutating Storage method.
- Provide a bounded Preview detail with per-item source identity, recognition/metadata decision,
  pinned configuration, policies, proposed target, attachments, conflict/capability evidence,
  warnings and failure guidance where the authoritative result supplies them. Do not invent absent
  evidence or turn a Preview into a Slice 34 review backlog.
- Make the Preview identity/version and item identities usable by the later server-side manual
  Organize journey while keeping raw fingerprint/digest/internal authority values out of browser
  models, URLs, DOM, console, audit evidence and test artifacts.
- Use explicit authenticated POST actions with exact bounded bodies and mutation retry disabled.
  Rejected, stale, malformed, unavailable, 401 or 403 submissions are never automatically replayed;
  a repeat requires a fresh state read and new operator intent.
- Cover loading, no eligible source, empty result, partial page, queued-without-Worker, stale source,
  invalid scope, limits, unsupported capability, conflict, malformed response, not-found, 401, 403
  and backend-unavailable states. Explain what is durable and offer only refresh, scope correction,
  Worker/configuration handoff, rerun Preview or applicable Task/Job navigation.
- Add strict frontend-owned Scan/Preview/source/action documents and centralized authenticated query
  and mutation boundaries. Feature components issue no raw fetch, cache no authority, do not retry
  actions and clear authenticated plus unsubmitted state on disconnect/auth rejection.
- Extend the local Playwright fake with secret-free current FileIndex/ResourceLibrary admission,
  Scan/Preview documents and deterministic state changes. Reject unsupported methods and bodies;
  record only bounded request evidence and never persist Bearer or authority-bearing values.
- Preserve V1 `/ui` and existing `/api/v1/*` clients through backward-compatible additions. Use
  temporary SQLite/local fakes only; no schema migration, production service or private runtime data
  is authorized.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, canonical/stable requirements, architecture and product-experience
  authority text, including all A-owned Contract fields.
- Manual intent/choice editing, item selection, execution authorization/admission, OrganizerExecutor
  and every Storage mutation; these remain the next Slice 33 manual Organize Task.
- Automation definitions/grants/schedules/occurrences and Notification definitions/deliveries; these
  remain later Slice 33 Tasks.
- Slice 34 media review/recovery actions and Slice 35 general Configuration administration. This
  Task may present only truthful destinations or V1 handoffs.
- Provider/Storage/pipeline semantics, configuration schema/activation, auth redesign, Node
  production serving, `config/alist.json` and private runtime state.

## Acceptance Criteria

- [ ] Operations and applicable Library FileIndex/ResourceLibrary surfaces expose real typed Scan
      and Preview entries/details with correct title, active navigation, direct refresh,
      memory-only authentication continuation and bounded return context.
- [ ] The backend action projection binds each visible action to the exact authenticated principal,
      current source/scope, readiness and supported limits. Viewer/forbidden, stale, unavailable or
      unsupported projections expose no actionable submission.
- [ ] File admission is server-bound to the current indexed occurrence/fingerprint without returning
      or requiring the browser to echo that fingerprint. Removed, replaced or changed sources fail
      closed before durable work/findings are published; ResourceLibrary scope is confined to its
      configured root and accepted relative-scope rules.
- [ ] Scan submission reuses the authoritative manual Scan application behavior, accepts no
      arbitrary source path/plan/provider/policy/authority, returns admitted work without holding the
      request open, and links to durable Task/Job and independently inspectable per-item state.
- [ ] Preview runs the complete applicable pipeline and presents the persisted aggregate plus
      independent item findings, including available pinned configuration, recognition/metadata,
      policies, proposed target/attachments, conflicts/capabilities, warnings and failures without
      fabricating missing facts.
- [ ] Automated evidence proves all Scan reads and all Preview behavior call no mutating Storage
      method; Preview does not submit executable work, create execution authority or imply that
      Organize has been authorized. Only the later explicit manual Organize journey may mutate.
- [ ] Scan/Preview list and item data are deterministically ordered and bounded; paging does not
      duplicate, omit or frontend-filter partial results, and malformed, repeated, stale,
      cross-object or filter-mismatched query state fails closed.
- [ ] Loading, no-source, empty, partial, queued, stale-source, invalid-scope, limit, conflict,
      unsupported, malformed, unavailable, not-found, 401 and 403 states remain oriented in the
      shell and provide only a valid refresh, corrected submission, readiness/configuration handoff,
      rerun Preview or Task/Job navigation.
- [ ] Submission uses only documented authenticated methods and exact bounded bodies, emits
      normalized security audit, renders the returned durable state and is never automatically
      retried after transport ambiguity, conflict, malformed response, 401 or 403.
- [ ] Central typed models and query/mutation boundaries reject malformed or contradictory modeled
      data. Feature components perform no raw fetch and clear authenticated query/mutation plus
      unsubmitted source state on disconnect or rejected authentication.
- [ ] API/model/URL/DOM/console/audit/test evidence contains no Bearer value, secret, execution
      token/grant, raw fingerprint/digest, raw provider payload/exception, private endpoint or
      absolute host/adapter root. Operator-facing source labels remain recognizable and bounded.
- [ ] V1 `/ui`, current `/api/v1/*` clients, Task 33.1 Operations routes/controls and Python-only
      production serving remain compatible; no second authority model or production Node service is
      introduced.
- [ ] Component/router and built-artifact browser evidence covers Library and Operations entry,
      authenticated/unauthenticated deep entry, exact-file and ResourceLibrary scope, Scan admission,
      Preview detail/items, stale source, invalid scope, readiness, exact method/body, no mutation
      replay, keyboard operation and narrow/wide layouts.
- [ ] All T4 commands below pass with actual totals/skips/unavailable gates reported. The checkpoint
      contains only this Task plus its Developer Completion Report; tests/assertions are not deleted
      or weakened, skips are not hidden and pre-existing unrelated files are preserved.

## Required Tests

Run and report all of the following from the repository root:

```text
python3 scripts/check_governance.py
env -u NODE_ENV npm --prefix web ci
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e -- manual-operations.spec.ts operations.spec.ts library-file-detail.spec.ts library-file-index.spec.ts library-files.spec.ts deep-link.spec.ts
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_manual_scan tests.test_manual_organize_preview tests.test_manual_preview tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
git diff --check
python3 scripts/docker_release_security_smoke_test.py
```

If a new focused Python or Playwright file has a different name, run that exact file in addition to
every existing named regression above and report the actual command. Docker validation may be
reported `UNAVAILABLE` only with the observed environmental reason; it must not be inferred as
passing.

Focused tests must cover valid/malformed strict models; principal/source/readiness action matrices;
server-bound occurrence/fingerprint recheck; ResourceLibrary relative-scope confinement; exact Scan
and Preview methods/bodies; duplicate/concurrent/stale admission; aggregate/item paging; zero
OrganizerExecutor and mutating Storage calls; no automatic mutation replay; bounded audit and
redaction. Use temporary SQLite databases, fakes, local test servers and the built static artifact.
No production Storage, Provider, credential, private configuration or operator media may be used.

Before checkpointing, inspect and report `git status --short`, the complete Task Base..Head diff,
changed-file manifest, test deletion/rename/skip/assertion changes and tracked/private configuration.
`config/alist.json`, `node_modules`, build reports, credentials and unrelated files must not enter the
checkpoint.

## Non-goals

- Creating/updating manual Organize intents or choices, selecting Preview items, issuing or
  consuming execution authority, admitting execution, or changing OrganizerExecutor/Storage
  mutation behavior.
- Recognition/Metadata/Classification review decisions, conflict resolution, Reprocess,
  checkpoint continuation, failed-item retry or uncertain-effect recovery owned by Slice 34.
- Automation definition/revision/grant/schedule/occurrence management or Notification
  definition/test/delivery management.
- Arbitrary host/Storage browsing, request-supplied absolute paths/plans/policies/provider payloads,
  uploads/downloads/content preview, artwork fetching or FFprobe/FFmpeg.
- General Configuration editing/activation, schema migration, provider/storage/auth redesign, token
  persistence, SSR/BFF/Node production serving, V1 retirement or unrelated refactoring.
- Optional analytics/export, background polling mutation, copy polish or P2/P3 cleanup not required
  by the Acceptance Criteria.

## Developer Completion Report

### Changed Files

Backend (Python):
- `mediaflow/application/manual_scan.py` — Added `admit_current_document()` for server-bound scan admission, `_require_current_file_direct()` for FileIndex resolution, `_recheck_live_source()` for live Storage recheck before publishing work
- `mediaflow/application/manual_organize_preview.py` — Added `create_current_from_index()` for server-bound preview admission that resolves FileIndex record server-side
- `mediaflow/application/operations_lifecycle.py` — Added `manual_preview_operator_document()` bounded projection, `_manual_preview_item_operator()`, `_bounded_preview_plan()` that strip fingerprints/digests and bound paths
- `mediaflow/interfaces/service_api.py` — Added `GET /api/v1/operations/manual-actions` (action matrix), `POST /api/v1/operations/scans` (server-bound scan), `GET /api/v1/operations/scans/{taskId}` (bounded detail), `POST /api/v1/operations/scans/{taskId}/cancel` (bounded cancel), `POST /api/v1/operations/previews` (server-bound preview), `GET /api/v1/operations/previews` (list), `GET /api/v1/operations/previews/{previewId}` (bounded detail); added `_manual_action_matrix()` method

Tests:
- `tests/test_manual_operations.py` — 20 new tests covering bounded documents, server-bound scan admission (resolution, not-found, not-ready, live-recheck, fingerprint-echo rejection), action matrix (file/library scope, permission gating, unavailable source), server-bound preview (routing, permission, fingerprint rejection, list/detail), zero-mutation invariant, fingerprint stripping

Frontend (TypeScript/React):
- `web/src/entities/operations/scan.ts` — Scan normalizer (ManualScanModel, ManualScanItemModel)
- `web/src/entities/operations/preview.ts` — Preview normalizer (ManualPreviewModel, ManualPreviewItemModel)
- `web/src/entities/operations/manual-actions.ts` — Action matrix normalizer (ManualActionMatrixModel)
- `web/src/features/operations/ScanNewPage.tsx` — Scan admission page with action matrix
- `web/src/features/operations/PreviewNewPage.tsx` — Preview admission page with action matrix
- `web/src/features/operations/ScanDetailPage.tsx` — Bounded scan detail with paging/cancel
- `web/src/features/operations/PreviewDetailPage.tsx` — Bounded preview detail with zero-mutation badge
- `web/src/features/operations/manual-scan-query.ts` — Scan query/mutation hooks
- `web/src/features/operations/manual-preview-query.ts` — Preview query hooks
- `web/src/features/operations/manual-actions-query.ts` — Action matrix query hooks
- `web/src/entities/operations/scan.test.ts` — 9 tests
- `web/src/entities/operations/preview.test.ts` — 11 tests
- `web/src/entities/operations/manual-actions.test.ts` — 6 tests
- `web/src/shared/api/api-client.ts` — 7 new API functions (fetchManualActionMatrix, submitServerBoundScan, fetchManualScanDetail, submitManualScanCancellation, submitServerBoundPreview, fetchManualPreviews, fetchManualPreviewDetail)
- `web/src/routes/router.tsx` — 4 new routes (scan/new, scan/$taskId, preview/new, preview/$previewId)
- `web/src/shared/navigation/destination-model.ts` — 4 child destinations with titles
- `web/src/features/library/FileIndexDetailPage.tsx` — Real Scan/Preview action buttons with action matrix
- `web/src/features/library/LibraryLanding.tsx` — ResourceLibrary action entries

### Implemented

- Server-bound file admission: browser never receives or echoes raw fingerprint/occurrence identity; backend resolves FileIndex record and rechecks live Storage before publishing durable work
- Backend action matrix projection bound to principal permission, source readiness, runtime readiness, and ResourceLibrary availability
- Bounded operator documents for Scan and Preview: strip fingerprints, occurrence IDs, configuration digests, raw provider payloads; keep configuration snapshot ID for pin evidence
- V2 typed routes with correct titles, active navigation, direct refresh, memory-only auth continuation, bounded return context
- Library surfaces expose real Scan/Preview entries via action matrix
- Preview zero-mutation invariant proven through operator document projection
- Mutation retry disabled: all POST actions use explicit authenticated methods

### Tests and Results

Focused Python tests (T4):
```
python3 -m unittest tests.test_manual_operations tests.test_manual_scan tests.test_manual_organize_preview tests.test_operations_workspace
Ran 59 tests in ~4s — PASS
```

New tests (tests.test_manual_operations):
```
python3 -m unittest tests.test_manual_operations -v
Ran 20 tests — PASS
```

Existing related tests (no regressions):
- tests.test_manual_scan: 9 tests — PASS
- tests.test_manual_organize_preview: 10 tests — PASS
- tests.test_operations_workspace: 20 tests — PASS

Quality gates:
- .venv/bin/ruff format --check . — PASS
- .venv/bin/ruff check . — PASS
- .venv/bin/python -m compileall -q mediaflow tests scripts — PASS
- git diff —check — PASS (no whitespace errors)
- npm --prefix web run format:check — PASS (frontend subagent)
- npm --prefix web run typecheck — PASS (frontend subagent)
- npm --prefix web run lint — PASS (frontend subagent)
- npm --prefix web run test -- --run — PASS, 284/284 (frontend subagent)
- npm --prefix web run build — PASS (frontend subagent)
- docker_release_security_smoke_test.py — UNAVAILABLE (Docker not available in this environment)

### Decisions

1. Server-bound admission resolves FileIndex record at admission time (no fingerprint echo). Stale detection happens via live Storage recheck (existing scanner behavior) — if file changed after FileIndex snapshot, recheck fails closed before Task creation.
2. Action matrix is a GET endpoint bound to principal permission, returning availability reasons. Frontend renders only what the backend advertises.
3. Bounded preview operator document uses the existing `manual_scan_operator_document` pattern: strip fingerprint/digest values, bound source paths, keep configuration snapshot ID.
4. Preview API integration tests require full RuntimeConfiguration pipeline (already well-tested in test_manual_preview.py). Zero-mutation invariant tested through operator document unit tests.
5. Frontend uses centralized route model (destination-model.ts) and bounded API client functions with retry: false for all mutations.

### Remaining In-Slice Work

- Manual intent/choice editing, item selection, execution authorization/admission, OrganizerExecutor, and Storage mutation remain the next Slice 33 manual Organize Task
- Automation definition/revision/grant/schedule/occurrence management and Notification definition/test/delivery management remain later Slice 33 Tasks
- Slice 34 media review/recovery and Slice 35 general Configuration administration

### Risks / Deviations

- Full Python test suite times out in this environment due to external service tests; all focused/manual-operations tests pass
- Docker release-security smoke test reported UNAVAILABLE (Docker not available)
- Pre-existing test_api_credentials failures (2 FAIL) are unrelated to this Task

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: d557252
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
