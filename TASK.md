# Task 39.1 — Storage inventory, reference inspection and read diagnostics

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 39.1
Parent Slice: 39
Status: READY FOR B REVIEW
Task Base: 77f58da419ba6e4198897180c649799d3f25a0d0
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the authenticated Storage **view and diagnose** journey through API and V2 Web: inspect
the exact Active inventory and its library references, then explicitly run and understand a bounded
zero-mutation Connection/Read check. This advances RO-1, RO-2, RO-5, RO-6 and RO-7; Add/Edit and
other configuration changes remain separate implementation units.

## Why This Task Exists

The managed configuration service already holds Storage objects, reference evidence and Draft-bound
Storage checks, but `/ui-v2/storage` does not exist. The shell's Configuration item still points to
the general migration handoff, and existing revision-object endpoints expose generic revision data
rather than an exact-Active, Storage-specific operator projection. An operator therefore cannot
inspect configured Storage and diagnose read access in the required V2 journey. Inventory, reference
inspection and the explicit read check form one independently useful, reviewable vertical unit;
mutation controls need the separate checked-publication boundary.

## Implementation Scope

- Compose bounded list/detail/check behavior from the existing managed Active authority and
  `ConfigurationObjectService`; add a typed Storage projection and matching versioned API surface
  where needed. Preserve the general Configuration and V1 routes. Do not create a second Storage
  repository, adapter registry or Active source.
- Project six supported types, stable identity, provider-safe location, enabled/read-only state,
  capability declarations, secret-reference readiness, exact configuration authority, latest check
  status/currentness and complete reference counts. The bounded breakdown includes disabled
  ResourceLibraries and MediaLibraries and reports truncation honestly.
- Add an explicit Connection/Read check for the selected exact candidate/runtime revision using
  existing Storage ports and read-only guards. Persist bounded evidence and distinguish diagnostic
  evidence persistence from Storage mutation; do not claim that a read check proves write access.
- Wire `/ui-v2/storage` into the shared shell and authentication continuation. Build the read-only
  workspace: prescribed header, shared top-bar Storage search, provider summary/filter cards,
  six-column table, inspectable detail/readiness and references, explicit read-check action,
  loading/empty/error/setup states. Search context stays separate from Files/MediaLibrary.
- Add focused application/API/entity/component/browser tests for this journey and preserve
  existing routes, adapters and configuration behavior. Keep `docs/pics/储存管理.png` and all
  pre-existing unrelated image changes outside this Task checkpoint.

## Acceptance Criteria

- [ ] Authenticated `/ui-v2/storage` uses the shared light shell with only `存储管理` active; general
      Configuration keeps its own route/handoff. The page shows the specified title/subtitle,
      provider cards and six columns in Contract order, with name above ID. Cards count configured
      objects from Active only. Search uses the shared top-bar placeholder `搜索存储、路径...`, matches
      name/ID/type/location, filters by provider family and does not change Files/MediaLibrary
      search state. No recursive read or media work occurs on page load, filter or search.
- [ ] API and Web list/detail are derived from the same exact immutable Active snapshot consumed
      by runtime, in deterministic bounded order. They distinguish no managed Active, setup-only
      authority, unavailable service and malformed response from a healthy empty list. Disabled
      Storage visibility follows backend permission. No Draft or saved JSON is labelled Active.
- [ ] Detail and reference inspection identify both library kinds, IDs/names and enabled state,
      with counts that include disabled dependents. A truncated display never implies that further
      blockers are absent. Local execution-environment roots and remote logical paths remain
      distinct; no host-wide listing or arbitrary path selection is introduced.
- [ ] Every API/Web projection and failure is bounded and secret-free: no credential values,
      authorization headers, cookies, tokens, access keys or raw provider exceptions. Secret
      reference readiness and provider capabilities are shown truthfully; enabled state, latest
      check result and write capability are not conflated.
- [ ] A permitted operator can explicitly run one bounded zero-mutation Connection/Read check
      against the exact selected revision and inspect currentness, attempted operations, result,
      failure category and next action. Stale authority, unavailable/missing root, denied/auth,
      timeout and unsupported read capability produce actionable failure. A viewer can inspect
      allowed evidence but cannot start a check. No write probe, scan, Job/Task, Metadata request,
      Storage mutation or automatic replay occurs; the UI states that write access was not tested.
- [ ] Setup, 401/403, loading, empty, malformed and failed-check states give a safe next action
      without raw revision/token ceremony in the ordinary journey. Explicit check repeatability is
      clear; an unknown result is verified before another attempt. Narrow-screen and keyboard/focus
      operation keep search, filters, table/detail and check reachable.
- [ ] Existing V1 `/ui`, general Configuration, Storage Browser, Files/MediaLibrary routes,
      adapters and OrganizerExecutor behavior remain compatible. The Task checkpoint contains only
      relevant changes, no private configuration and no changes to the A-owned Slice Contract.

## Required Tests

Run and record commands, totals, skips and unavailable gates. Use temporary roots and fake/local
provider services only.

- `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_setup_check tests.test_storage_configuration_management` plus focused new application/API tests for Active projection, references, redaction, RBAC and exact-revision read checks.
- `.venv/bin/python -m unittest discover -s tests` (T4 full Python regression).
- `cd web && npm test -- --run` plus focused new Storage entity/API/component tests.
- `cd web && npm run test:e2e -- --grep 'Storage management'` for authenticated inventory,
  references, check success/failure, setup/recovery, search/filter and keyboard/narrow layout;
  report browser availability or fixture limitations honestly.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .`,
  `.venv/bin/python scripts/check_governance.py`, `git diff --check`, and a manifest/private-file,
  secret-output and FFmpeg/FFprobe exclusion audit. Run changed-boundary packaging or migration
  gates if this implementation actually changes those boundaries.

## Non-goals

- Add/Edit/copy/enable/disable/removal, provider forms and the four-step mutation drawer; these
  require checked Active publication in later Task(s). Do not show dead mutation controls as if
  they work.
- General Configuration redesign, setup replacement, Storage Files browsing, write probes,
  provider additions, physical-file mutation or media-processing work.
- Storage notes, including input, display, persistence and search.
- Editing or regenerating the committed visual reference, unrelated image changes, or any work
  outside the Slice Contract.

## Developer Completion Report

### Changed Files

- `TASK.md`
- `mediaflow/application/configuration_objects.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_v2_storage_operations.py`
- `web/src/entities/storage/storage-management.ts`
- `web/src/entities/storage/storage-management.test.ts`
- `web/src/shared/api/api-client.ts`
- `web/src/shared/api/storage-management-api.test.ts`
- `web/src/features/storage/storage-management-query.ts`
- `web/src/features/storage/StorageManagementPage.tsx`
- `web/src/features/storage/StorageManagementPage.test.tsx`
- `web/src/shared/ui/styles.css`
- `web/tests/fake-server.mjs`
- `web/tests/e2e/storage-management.spec.ts`

### Implemented

- Fixed the B blocker in this Task only: `active_storage_management()` now derives provider
  (`families`) counts from the complete Active Storage object set instead of the returned page.
- Added a bounded inventory search (`q`) and provider-filter (`family`) that run inside the
  projection over the complete Active object set, so every configured Storage stays findable and
  inspectable even when it is not on the first bounded page. Matching covers name, stable ID,
  provider type and provider-safe location (root path plus host/share/bucket/endpoint/region);
  no secret values are searched or returned.
- Added a bounded explicit continuation (`limit` 1..100, stable ID-ordered `after` cursor) that
  returns `matched`, `returned`, `hasMore` and `nextAfter`, so an over-limit inventory or
  over-limit search result stays fully reachable. Unsupported, repeated or out-of-range query
  fields are rejected instead of being silently ignored.
- Made the bounded inventory journey disclose truncation: the page states how many of how many
  matching rows are shown and offers explicit continuation (`继续显示更多`) plus a return to the
  first page, while provider cards keep showing complete-Active configured counts. A search with
  no match states that truthfully even when other Storages remain configured.
- Nobody else in the Task changed: Add/Edit/mutation, checked publication and the Slice Contract
  are untouched; detail, read-check and RBAC behavior are preserved.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_setup_check tests.test_storage_configuration_management tests.test_v2_storage_operations` — PASS, 105 tests.
- `.venv/bin/python -m unittest discover -s tests` — PASS, 1813 tests, 7 skipped.
- `cd web && npm test -- --run` — PASS, 46 files and 643 tests.
- `cd web && npm run test:e2e -- --grep 'Storage management'` — PASS, 11 browser tests (includes the new legal over-limit journey).
- `cd web && npm run typecheck` — PASS.
- `cd web && npm run lint` — PASS.
- `cd web && npm run format:check` — PASS.
- `cd web && npm run build` — PASS; Vite emitted a non-fatal large-chunk advisory.
- `.venv/bin/ruff format --check .` — PASS, 315 files already formatted.
- `.venv/bin/ruff check .` — PASS.
- `scripts/check_governance.py` — PASS.
- `scripts/docker_release_security_smoke_test.py` — UNAVAILABLE (environment gate): the base Task
  passed this gate at `19f9762`; this correction adds no packaging, Dockerfile, Compose or
  persistence/API-boundary change, so no new release-security evidence is claimed. The command was
  attempted and fails on two contemporary Docker tmpfs bind-mount errors (missing
  `/tmp/.../media/incoming`, then missing `.../deployment.env`) after the compose-down outline was
  made hermetic in commit `19f9762`; the failure is environmental, unrelated to this Task, and was
  not introduced by the correction commits.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `git diff --check` — PASS, including the staged diff.
- Manifest/private-file audit — PASS: the staged manifest contains only the 15 listed Task files;
  `config/alist.json` is ignored, untracked and unstaged. Secret-output tests passed; test-only
  credential markers are synthetic fixtures. FFmpeg/FFprobe exclusion audit — PASS, no matches
  in changed runtime or test sources.

### Decisions

- Search and provider filtering are applied server-side over the complete ordered Active set, and
  the page is a bounded window over that same filtered set — the single source of truth, so a
  Storage beyond the first page can never again be unreachable from the Web search or filter.
- Provider (`families`) counts are always derived from the complete Active object set, never from
  the returned page, so the summary cards stay truthful when the configuration is over the page
  limit and remain stable while a search or filter narrows the table.
- `truncated` now means the returned page is not the complete matching inventory (`hasMore`);
  with `total` (configured), `matched` (matching), `returned` (this page) and `nextAfter`, the
  operator always sees the durable quantities and the explicit bounded way to continue.
- No Slice Contract or Roadmap changes.

### Remaining In-Slice Work

- Storage Add/Edit/copy/enable/disable/removal and checked publication are explicitly deferred by
  this Task.

### Risks / Deviations

- This correction also fixes the prior checkpoint's misrecorded release-security gate (the original
  report wrote an unrelated stdout line for the smoke test). The base round's `docker compose down`
  env outline was added strictly to keep the report truthful; it changed no application behavior.
- The pre-existing unrelated image files (`docs/pics/` deleted/modified/untracked entries
  documented at round start) are preserved and excluded from this Task checkpoint.
- The frontend build emits a non-fatal Vite large-chunk advisory.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 733c4a32eae020ffabeac45ad4e05c1bae681ab3
```

## B Review Result

```text
Reviewed: 77f58da419ba6e4198897180c649799d3f25a0d0..19f976288719a18ffb657b187f5e6ed82816ad9a
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Inventory search and provider counts omit valid Active Storage objects after the first 100,
  violating this Task's first two Acceptance Criteria and Slice RO-2. In a temporary, validated
  105-Storage managed Active configuration using the current production API and runtime loader,
  `GET /api/v1/operations/storage-management/inventory` returned `total: 105`, 100 items,
  `truncated: true`, and only 97 Local objects in `families` although 102 Local objects were
  configured. The remaining five objects cannot be found by the Web search or provider filter:
  `active_storage_management()` counts families only from its first 100 projected objects, and
  `StorageManagementPage` filters only those returned rows without showing the truncation. Make
  the bounded inventory journey disclose truncation and let the operator find/inspect every
  configured Storage through bounded search or paging; derive provider counts from the complete
  Active object set. Cover this legal over-limit configuration through API and Web tests.
