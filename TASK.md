# Task 41.6 — Rules object identity across lifecycle and deep links

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 41.6
Parent Slice: 41
Status: PLANNED
Task Base: 77f4d931bd91f9bd38b7b2ecb75ebe99f320ced7
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An administrator can manage a rule/policy object with any ID already accepted by the production
rules command authority: create, revisit, edit, copy, enable/disable where supported, inspect
references and safely remove it through V2. Its explicit edit route survives direct entry, refresh
and reconnect without changing its identity. This completes the remaining identity-dependent parts
of RO-1, RO-3, RO-4, RO-5, RO-7 and RO-8 while preserving RO-2 and RO-6.

## Why This Task Exists

Task 41.5 passed B review at implementation Head
`4ad2a2105d5caa12aff4e082d64311098850a555`; Slice outcomes remain incomplete, so the
next action is a new coherent Task. Its original Task Base remains unchanged.

Slice reevaluation found a current production journey failure, separate from Task 41.5's frozen
object-editing boundary. The backend rules identifier contract and create form accept bounded IDs
containing `+`, `@`, internal spaces and dots. The Rules API client, edit-page guard and shared
navigation use incompatible generic identifier restrictions; Python's static boundary also treats
a dotted final route segment as an unknown asset.

B reproduced this against the current built V2 artifact, production `MediaFlowApi`, real temporary
SQLite repositories and real Local Storage with valid roots. Web Save successfully published
`proof+type`, `proof@type`, `proof type` and `proof.type`. The first three then displayed
`无法打开该对象` on Edit. Copy and confirmed Disable for `proof+type` failed locally before their
API request; Remove reported `0` references as a deletion blocker without obtaining impact evidence.
`proof.type` opened in SPA navigation but refreshing its edit URL returned HTTP 404. These violate
Slice AC-3, refresh-safe RO-1, management RO-3/RO-5 and API/Web parity; they are not future-adapter or
invalid-configuration scenarios.

The next unit is the shared object-identity boundary across seven families and all existing lifecycle
surfaces, rather than separate tasks for characters, regexes, actions or tests. Reuse the existing
backend identity contract and route authority; no new configuration lifecycle or routing framework
is needed.

## Implementation Scope

Application identity authority → API client → typed forms/inventory/full-page Edit → shared
navigation/auth continuation → Python V2 artifact serving → regression and browser evidence.

- Make Rules-specific identity validation consistent with IDs already accepted by
  `RulesWorkspaceCommandService`. Apply it to existing edit/copy/impact reads and Save/toggle/remove
  commands, plus applicable candidate/test identity handling. Preserve immutable ID on Edit and the
  existing backend-selected new-ID copy behavior. Audit all seven families for this same boundary.
- Preserve the exact ID across route construction, percent encoding/decoding, route matching and
  authenticated continuation. Direct entry, refresh and reconnect must open the same full-page Edit
  context; no coercion, ID replacement or silent navigation to a different object. Keep existing
  unsaved-input protection and inventory return-family context.
- Narrowly allow supported Rules edit routes with legal dotted IDs through Python's built-artifact
  SPA fallback. Keep traversal confinement, missing-artifact failure, unknown-asset refusal and
  allowlisted file serving intact. Do not globally treat arbitrary dotted paths as SPA routes.
- Complete lifecycle outcomes for those objects using existing exact-Active optimistic authority,
  checked activation, RBAC, audit and reference protection. Inspection remains read-only; Copy opens
  a candidate, and each mutation still requires explicit Save/confirmation. An impact-read failure
  must remain a failed read with a safe next action, not fabricated reference evidence.
- Add focused tests and a built-artifact browser proof using the real Python serving boundary and
  legal production API/Local configuration. Use isolated temporary resources and throwaway test
  identities; a fake that serves every pathname cannot prove the Python refresh fix.

Frozen boundaries: rule operators/domain fields, policy evaluation, preview engines, configuration
lifecycle semantics, OrganizerExecutor, Storage mutation, Scan/Task/Job execution, unrelated routes
and page redesign, V1 retirement, all reference images and `config/alist.json`.

## Acceptance Criteria

- [ ] IDs currently accepted by backend rule commands are accepted consistently by V2 lifecycle
      reads/commands and identity-bearing routes across all seven families. `+`, `@`, internal space,
      dot, ordinary IDs and the existing length boundary are covered without silently narrowing the
      backend contract, changing persisted IDs or relaxing unrelated generic identity guards.
- [ ] Through Web, an independent object with such an ID can publish, reopen for Edit, publish a
      name-only change with its ID unchanged, copy to a distinct candidate and Save, explicitly
      disable/enable where supported, and remove when unreferenced. Outcomes show actual Active
      publication; candidates and failed commands remain distinct. Referenced removal stays blocked
      by real backend evidence and leaves Active/history/media unchanged.
- [ ] Edit supports SPA navigation and direct production `/ui-v2/rules/edit/<family>/<encoded-id>`
      entry, refresh and authenticated reconnect. The same ID and family are retained, existing
      correctable-input protection works, and returning reaches the originating inventory. Legal
      dotted IDs receive the built entry document rather than HTTP 404.
- [ ] Invalid/oversized IDs, slash/backslash/path traversal, unsupported family/depth, malformed
      encoding and forged continuation remain safely rejected or bounded by the appropriate existing
      route/API authority. Unknown assets and missing artifacts retain fail-closed serving. A Rules
      fix does not broaden other destination continuations or expose files outside the artifact.
- [ ] Copy/impact/Edit reads and navigation create no Draft, Provider call, Task/Job or Storage
      mutation. Mutation permissions, exact-Active concurrency, audit/redaction, unknown-outcome
      verification/no automatic replay and reference-protected deletion remain backend-authoritative.
      Failed impact reads do not claim a zero-reference object is referenced or permit deletion.
- [ ] Focused identity/lifecycle/security tests, a browser journey through the real built-artifact
      serving boundary, related regressions and all T4 gates pass with actual counts and skips.
      The checkpoint contains only this coherent correction.

## Required Tests

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py tests/test_v2_rules_workspace_commands.py tests/test_v2_rules_workspace_previews.py tests/test_v2_ui.py tests/test_api_security.py`
  plus new focused tests if placed elsewhere. Cover accepted IDs and invalid input, all-family
  identity roundtrips, exact-Active lifecycle/reference protection, and the real static route boundary.
- `npm --prefix web test -- --run src/entities/rules/rules-workspace.test.ts src/shared/api/rules-workspace-api.test.ts src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/shared/navigation/destination-model.test.ts`
  plus added shared identity/form tests. Include encoding/continuation boundaries and truthful impact
  failure, with ordinary route/identifier regressions preserved.
- Add a deterministic Rules identity browser journey, run
  `npm --prefix web run test:e2e -- --grep 'rules workspace|rules readiness|rules identity'`, and
  record its actual count. Also run and document a reproducible automated browser proof against the
  current built artifact served by production Python: legal temporary Local/SQLite configuration,
  create → Edit → refresh/reconnect → name-only Save → copy → toggle → safe remove/reference block.
  Explicitly include `+`, `@`, space and dotted-ID route cases. The proof must not depend solely on
  the permissive fake-server SPA fallback or require real credentials/services/user media.
- `npm --prefix web test -- --run`, `npm --prefix web run typecheck`,
  `npm --prefix web run lint`, `npm --prefix web run format:check`, and
  `npm --prefix web run build`.
- `.venv/bin/python -m unittest discover -s tests`,
  `.venv/bin/python -m compileall -q mediaflow tests scripts`,
  `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`,
  `python3 scripts/check_governance.py`, and `git diff --check`.
- `python3 scripts/docker_release_security_smoke_test.py` with temporary resources visible to its
  container mounts, plus Base..Head scope/private-file and unchanged-reference-image audit. Run
  resource-heavy full gates serially; report unavailable gates/skips and any failure by test name.

## Non-goals

- Changing valid persisted IDs, reducing the supported identity grammar, or adding new object fields,
  operators, provider integrations, policy semantics or configuration lifecycle states.
- General route/auth redesign, widening unrelated identifier validation or making arbitrary asset
  paths fall back to HTML.
- Media execution, migration of historical snapshots, V1 retirement, unrelated page/Storage work.
- Optional cleanup, duplicate-test removal, wording polish or additional proof without a current
  acceptance need; no separate Task for any one ID character, assertion or error message.

## Developer Completion Report

### Changed Files

- `mediaflow/interfaces/v2_ui.py` — narrow allowlisted rules-edit SPA entry exception for legal
  dotted IDs; unknown dotted assets, multi-suffix shapes, unsupported families and depth still fail
  closed.
- `mediaflow/application/rules_workspace_commands.py` — new `rules_family_section(family)` helper so
  every consumer resolves a family's persisted section (`typeBindings` → `recognitionTypePolicies`).
- `mediaflow/interfaces/service_api.py` — `_rules_save_response` now resolves the published object
  through `rules_family_section(family)` (fixes every successful typeBindings Save previously
  failing its own response projection with `typeBindings is missing`); import updated.
- `web/src/shared/api/api-client.ts` — `isRulesObjectId` exported, mirroring the backend
  `RulesWorkspaceCommandService` identifier contract (`+`, `@`, internal space, dot, 64-char bound);
  applied to the six rules object reads/commands only; the generic `isSafeIdentifier` task/job/job
  guards are untouched.
- `web/src/features/rules/RulesEditPage.tsx` — the route identity guard now uses the backend
  rules identity contract; rejection copy updated; no other behavior change.
- `web/src/shared/navigation/destination-model.ts` — `/rules/edit/$family/$objectId` instances are
  validated segment-by-segment against the backend rules grammar after `decodeURIComponent`
  (malformed encoding fails closed); all other dynamic destinations keep `INSTANCE_SEGMENT`.
- `web/tests/fake-server.mjs` — real-route rules object lifecycle (create/edit/copy/impact/state/
  remove) with the backend identifier grammar and per-session exact-Active authority;
  `form-authority` served from the new fixture; static `/ui-v2/` serving mirrors the production
  dotted-ID entry exception; lifecycle objects merge into the inventory document.
- `web/tests/fixtures/rules-form-authority.json` — new cross-boundary fixture captured from the real
  Python API (identity fields pinned to stable placeholders).
- `tests/test_v2_ui.py` — dotted-ID entry document + narrow-allowlist serving tests.
- `tests/test_v2_rules_workspace_commands.py` — three new identity tests: all seven families
  lifecycle round-trip through the real API routes with `+`/`@`/space/dot and the 64-char bound;
  zero Provider/Task/Storage side effects and secret-free documents; invalid identity shapes fail
  closed without publishing.
- `web/src/shared/api/rules-workspace-api.test.ts` — identifier grammar matrix, route encoding,
  pre-flight rejection without requests, command acceptance with immutable ID, candidate-ID mismatch
  refusal.
- `web/src/shared/navigation/destination-model.test.ts` — rules edit deep links resolve every
  backend-legal ID; malformed encoding/depth/oversize fail closed; other destinations unchanged.
- `web/src/features/rules/RulesEditPage.test.tsx` — direct entry of percent-encoded `+`/`@`/space/
  dot edit routes opens the exact object; out-of-contract identities show the safe rejection with
  zero object reads.
- `web/tests/e2e/rules-identity.spec.ts` — new deterministic Playwright journey (dotted-ID refresh/
  reconnect; plus/at/space/dot direct entry; full publish→edit→name-only Save→copy→disable→remove).
- `scripts/rules_identity_browser_proof.py` — new automated browser proof against the real Python
  API serving the built artifact with temporary legal Local/SQLite configuration.

### Implemented

- Browser/API identity parity: the six V2 rules object reads/commands and the edit-route guard now
  accept exactly the IDs the backend rules command authority accepts; `+`, `@`, internal space and
  dot IDs publish, reopen for edit, save name-only with an immutable ID, copy to a distinct
  candidate, toggle and remove through the real API routes.
- The `typeBindings` family Save response no longer fails after a successful publication
  (`_rules_save_response` resolved the operator-facing family name as a document section).
- Refresh/direct entry of `/ui-v2/rules/edit/<family>/<encoded-id>` works for dotted IDs through
  the real Python built-artifact boundary via one anchored allowlisted route shape; unknown assets,
  `.bak`/`.env`-like suffixes, extra depth, unsupported families and traversal still 404.
- Authenticated continuation resolves the same identity-bearing edit route after reconnect; the
  shared navigation model decodes and validates the identity segment against the backend contract.
- Failed impact reads remain failed reads; reference-protected removal and all safety invariants are
  unchanged and asserted (zero Provider/Task/Storage side effects, secret-free documents, no media
  mutation).

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py tests/test_v2_rules_workspace_commands.py
  tests/test_v2_rules_workspace_previews.py tests/test_v2_ui.py tests/test_api_security.py`
  → PASS (126 passed, 114 subtests).
- `npm --prefix web test -- --run src/entities/rules/rules-workspace.test.ts
  src/shared/api/rules-workspace-api.test.ts src/features/rules/RulesWorkspacePage.test.tsx
  src/features/rules/RulesEditPage.test.tsx src/shared/navigation/destination-model.test.ts`
  → PASS (69 passed).
- `npm --prefix web run test:e2e -- --grep 'rules workspace|rules readiness|rules identity'`
  → PASS (10 passed, including 3 new `Rules object identity` journeys).
- `python3 scripts/rules_identity_browser_proof.py` (automated built-artifact browser proof against
  the real Python serving boundary with temporary legal Local/SQLite configuration; includes `+`,
  `@`, space and dotted-ID route cases and the fail-closed static probes)
  → PASS (`identity journey: {"ok":true,"writes":4}`; `static serving boundary: {"ok":true}`).
- `npm --prefix web test -- --run` → PASS (55 files, 823 tests).
- `npm --prefix web run typecheck` → PASS; `npm --prefix web run lint` → PASS;
  `npm --prefix web run format:check` → PASS; `npm --prefix web run build` → PASS.
- `.venv/bin/python -m pytest -q tests/` → PASS (2008 passed, 7 skipped, 1526 subtests).
- `.venv/bin/python -m unittest discover -s tests` → OK (2015 tests, 7 skipped).
- `.venv/bin/python -m compileall -q mediaflow tests scripts` → PASS.
- `.venv/bin/ruff format --check .` → PASS; `.venv/bin/ruff check .` → PASS.
- `python3 scripts/check_governance.py` → PASS; `git diff --check` → PASS.
- `python3 scripts/docker_release_security_smoke_test.py` → PASS ("Release-security smoke acceptance
  passed."). First attempt failed on a host-environment limitation (the Docker daemon cannot bind-mount
  files from `/tmp` in this session: `bind source path does not exist` for the harness's own generated
  temp config). Re-run with `TMPDIR` pointed at a repository-local directory; the harness, its
  temporary resources and its assertions were unchanged.

### Decisions

- The browser identifier guard is a new rules-specific `isRulesObjectId` that mirrors the backend
  contract exactly instead of widening the generic `isSafeIdentifier`: other journeys (tasks, jobs,
  notifications) keep their stricter URI-safe grammar, and only the rules surfaces relax to the
  backend's own published contract.
- The navigation model validates the concrete rules-edit identity segment after
  `decodeURIComponent`, so a percent-encoded deep link matches the same grammar as SPA navigation;
  malformed encoding fails closed. The route shape (family allowlist, depth) stays the navigation
  model's job while family validity remains the page/backend authority.
- The Python static boundary gains one anchored exception (`_is_rules_edit_route`) instead of a
  generic dotted-path fallback: exact prefix, exactly one identity segment, allowlisted family,
  bounded length, and known asset-file suffixes (`.bak`, `.env`, …) excluded. All pre-existing
  fail-closed behaviors are asserted unchanged.
- `rules_family_section` is a single shared mapping so the API Save response, projections and future
  consumers cannot re-derive the `typeBindings` → `recognitionTypePolicies` section differently.
- The e2e fake now serves the object lifecycle on the real `/api/v1/operations/rules/objects/*`
  routes with the real identifier grammar and per-session exact-Active authority, and its static
  serving mirrors the production dotted-ID exception, so the browser proof cannot pass against a
  permissive fake. The form-authority document is a captured cross-boundary fixture
  (`rules-form-authority.json`), matching the existing readiness-fixture pattern.
- The proof script uses the production first-activation path (`config import` → `validate` →
  `activate`) on temporary resources and asserts the four explicit write commands it observes, so no
  hidden mutation channel is used.

### Remaining In-Slice Work

- The Task Base..Head identity work covers the seven rules families and the serving boundary;
  whether every Slice Required Outcome now reads satisfied is B's reevaluation after this review.
- Settings rule-readiness and the rules workspace were corrected in Task 41.5; no further
  readiness/handoff work was touched here.

### Risks / Deviations

- The docker release-security smoke required a repository-local `TMPDIR` in this session because the
  Docker daemon here cannot bind-mount files from `/tmp`; the harness itself ran unmodified and
  passed. Operators with a normal daemon layout are unaffected.
- `web/tests/fixtures/rules-readiness.json` was reformatted (prettier) with no content change beyond
  re-serialization; the fixture-contract test against the real API passes.
- The fake server's per-session object lifecycle is test tooling only; production authority remains
  the Python application services.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 101b9236e97b8974729653593d901b0a04249d2f
```

## B Review Result

```text
Reviewed: NOT REVIEWED
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
