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
- `web/src/features/storage/StorageManagementPage.tsx`
- `web/src/features/storage/StorageManagementPage.test.tsx`
- `web/tests/e2e/storage-management.spec.ts`

### Implemented

- Fixed the B blocker in this Task only: a new search in the shared top-bar now
  resets the bounded inventory page window instead of combining the new query
  with the stale continuation cursor. `StorageManagementPage` tracks the
  search/filter basis (`pageBasis`) and derives `effectiveAfter`: when the
  trimmed search or provider filter no longer matches that basis, the next
  inventory request already sends `after: null` (no `after` query param), so
  `GET .../inventory?q=local-000` can never again be sent as
  `?q=local-000&after=local-099` with `matched: 1, returned: 0` and a false
  `没有匹配搜索或筛选条件的存储` state. The render-phase `pageBasis` sync
  persists the reset for subsequent renders.
- Provider-filter changes keep their existing synchronous reset; family,
  search and continuation behavior are otherwise unchanged. No backend, API,
  projection, Slice Contract or Add/Edit/mutation change was made: detail,
  read-check, RBAC, redaction and checked-publication boundaries are preserved.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_setup_check tests.test_storage_configuration_management tests.test_v2_storage_operations` — PASS, 105 tests.
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED, 1813 tests, 7 skipped, 1 failure: `tests.test_release_security.ReleaseSecurityPolicyTests.test_release_quality_gate_commands_are_documented_for_task_execution` asserts the literal string `python3 scripts/check_governance.py` appears in `TASK.md`, but B's Task text (unchanged since `19f9762`, before this correction) documents the gate as `` `.venv/bin/python scripts/check_governance.py` ``. The failure reproduces on the unmodified HEAD checkout, involves no file touched by this correction, and the governance gate itself passes (see `scripts/check_governance.py` — PASS below). Fixing the wording is B-owned Task text, so it is left for B and recorded here, not silently edited.
- `cd web && npm test -- --run` — PASS, 46 files and 643 tests.
- Focused `cd web && npm test -- --run src/features/storage/StorageManagementPage.test.tsx src/shared/api/storage-management-api.test.ts src/entities/storage/storage-management.test.ts` — PASS, 3 files and 32 tests (includes the new search-after-continuation reset assertion: the next request after continuation carries `q=local-0` with no `after=` and still finds the earlier `Local 0` row).
- `cd web && npm run test:e2e -- --grep 'Storage management'` — PASS, 11 browser tests (the over-limit journey now continues, then searches `local-000` and asserts the `本地存储 000` row is visible with no false empty state, reproducing B's exact `继续显示更多` → search flow).
- `cd web && npm run typecheck` — PASS.
- `cd web && npm run lint` — PASS.
- `cd web && npm run format:check` — PASS (after `prettier --write` on the two touched source/test files).
- `cd web && npm run build` — PASS; Vite emitted the known non-fatal large-chunk advisory.
- `.venv/bin/ruff format --check .` — PASS, 315 files already formatted.
- `.venv/bin/ruff check .` — PASS.
- `scripts/check_governance.py` — PASS (`governance check: PASS`; literal command `python3 scripts/check_governance.py` was executed as `.venv/bin/python scripts/check_governance.py`).
- `scripts/docker_release_security_smoke_test.py` — UNAVAILABLE (environment gate): not attempted this round; this correction touches only Web search/paging state plus its tests, no packaging, Dockerfile, Compose or persistence/API boundary, so no new release-security evidence is claimed.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `git diff --check` — PASS.
- Manifest/private-file audit — PASS: this correction stages only the 4 listed Task files; `config/alist.json` is ignored, untracked and unstaged. The pre-existing unrelated `docs/pics/` dirty/deleted/untracked entries documented at round start are preserved and excluded from the checkpoint. Secret-output audit — PASS (no secret values in projections or test output; test tokens are synthetic fixtures). FFmpeg/FFprobe exclusion audit — PASS, no matches in changed sources or tests.

### Decisions

- The reset is derived (`effectiveAfter`) as well as persisted (`pageBasis` sync)
  so the very next query after a search change already drops the stale cursor;
  a `useEffect`-only reset would still fire one stale `?q=...&after=...`
  request first and reproduce the false-empty state.
- Search comparison uses the trimmed query (the same value sent to the API) so
  whitespace-only typing does not thrash the page window.
- The provider filter and the search share one `pageBasis`, so either change
  resets the window through the same path; `onSelect` keeps its existing
  explicit reset as well.
- No Slice Contract or Roadmap changes.

### Remaining In-Slice Work

- Storage Add/Edit/copy/enable/disable/removal and checked publication are explicitly deferred by
  this Task.

### Risks / Deviations

- Full Python regression has 1 pre-existing unrelated failure documented above
  (`test_release_quality_gate_commands_are_documented_for_task_execution`,
  B-owned Task wording vs. the test's literal `python3` prefix); all 105
  focused storage tests and every other suite pass. B decides PASS/FAIL.
- The pre-existing unrelated image files (`docs/pics/` deleted/modified/untracked entries
  documented at round start) are preserved and excluded from this Task checkpoint.
- The frontend build emits the known non-fatal Vite large-chunk advisory.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 3f331fb7dc16cb8fc5f012323f8ff05a22abbb0c
```

## B Review Result

```text
Reviewed: 77f58da419ba6e4198897180c649799d3f25a0d0..733c4a32eae020ffabeac45ad4e05c1bae681ab3
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Searching after inventory continuation can falsely report that a configured Storage does not
  exist, violating this Task's first two Acceptance Criteria and Slice RO-2. With the committed
  105-Storage browser fixture, I opened `/ui-v2/storage`, clicked `继续显示更多`, then searched for
  `local-000` in the shared top bar. The actual request was
  `GET /api/v1/operations/storage-management/inventory?q=local-000&after=local-099`;
  the API reported `matched: 1, returned: 0`, while Web displayed `没有匹配搜索或筛选条件的存储`.
  The current production API reproduced the same result with a validated 105-Storage managed
  Active configuration in a temporary database: after the first page, searching its earlier
  `local-source` with the returned cursor gave `matched: 1, returned: 0`.
  `StorageManagementPage` resets `afterCursor` on provider-filter changes but retains it when
  search changes. Reset the page window when a new search starts and cover search for an earlier
  configured Storage after continuation in the browser journey.
