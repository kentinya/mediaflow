# Task 41.6 — Rules object identity across lifecycle and deep links

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 41.6
Parent Slice: 41
Status: FIX REQUIRED
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
  `npm --prefix web run test:e2e -- tests/e2e/rules-readiness.spec.ts tests/e2e/rules-identity.spec.ts`,
  and record its actual count and selected suite names. Select the files explicitly: the original
  case-sensitive grep selected only the ten readiness tests, not `Rules object identity`; correct
  the completion report's claim that those ten included three identity tests. Also run and document
  a reproducible automated browser proof against the
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

- TASK.md — B's same-Task blockers and the Developer Completion Report.
- mediaflow/application/rules_workspace_commands.py and mediaflow/interfaces/service_api.py — shared family-to-section resolution fixes the typeBindings Save response projection.
- mediaflow/interfaces/v2_ui.py and tests/test_v2_ui.py — exact Rules edit route matching against the backend's decoded 1–64 character identity grammar; fail-closed coverage for invalid IDs, unknown assets, traversal and missing artifacts.
- web/src/shared/api/api-client.ts, web/src/shared/api/rules-workspace-api.test.ts, web/src/shared/navigation/destination-model.ts, web/src/shared/navigation/destination-model.test.ts, web/src/features/rules/RulesEditPage.tsx, and web/src/features/rules/RulesEditPage.test.tsx — Rules identity parity across reads, commands, encoded routes and authenticated continuation.
- web/src/entities/rules/rules-form.ts, web/src/features/rules/RulesWorkspacePage.tsx, and web/src/features/rules/RulesWorkspacePage.test.tsx — failed reference-impact reads stay distinct from real reference evidence, offer an explicit reread and keep removal unavailable.
- tests/test_v2_rules_workspace_commands.py — seven-family identity and lifecycle coverage.
- web/tests/fake-server.mjs, web/tests/fixtures/rules-form-authority.json, and web/tests/e2e/rules-identity.spec.ts — bounded lifecycle fake and browser coverage for legal file-like IDs and stale impact recovery.
- scripts/rules_identity_browser_proof.py — real Python serving-boundary browser proof using temporary Local/SQLite resources.

### Implemented

- Rules object IDs accepted by the backend now remain unchanged through all seven family lifecycle reads and commands, Edit routes, refresh, reconnect and API encoding. The typeBindings Save response resolves its published object from the correct persisted configuration section.
- The built-artifact boundary serves the entry document only for an exact supported Rules edit route whose WSGI-decoded identity matches the backend's 1–64 character grammar. Legal +, @, spaces, dots and file-like suffixes remain usable; invalid exact routes, traversal, missing artifacts and unknown dotted assets fail closed.
- A failed reference-impact read is represented as unavailable evidence, with a read-specific explanation and explicit reread action. Removal cannot be confirmed until a successful current impact read shows no references; stale-object, permission and transport failures issue no delete request.
- The real Python-boundary browser proof covers +, @, space, dot, proof.js, proof.env and proof.type.bak, direct entry and refresh/reconnect, unknown assets and traversal, plus the concurrent-removal recovery path.

### Tests and Results

- .venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py tests/test_v2_rules_workspace_commands.py tests/test_v2_rules_workspace_previews.py tests/test_v2_ui.py tests/test_api_security.py → PASS (126 passed, 114 subtests).
- .venv/bin/python -m pytest -q tests/test_v2_ui.py → PASS (13 passed).
- npm --prefix web test -- --run src/entities/rules/rules-workspace.test.ts src/shared/api/rules-workspace-api.test.ts src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/shared/navigation/destination-model.test.ts → PASS (71 passed); after the read-specific copy change, npm --prefix web test -- --run src/features/rules/RulesWorkspacePage.test.tsx → PASS (32 passed).
- npm --prefix web run test:e2e -- tests/e2e/rules-readiness.spec.ts tests/e2e/rules-identity.spec.ts → PASS (14 passed: 4 Rules object identity, 10 Rules readiness and Settings handoff).
- python3 scripts/rules_identity_browser_proof.py → PASS (identity journey: {"ok":true,"writes":4}; static serving boundary: {"ok":true}).
- npm --prefix web test -- --run → PASS (55 files, 825 tests).
- npm --prefix web run typecheck → PASS; npm --prefix web run lint → PASS; npm --prefix web run format:check → PASS; npm --prefix web run build → PASS.
- .venv/bin/python -m pytest -q tests/ → PASS (2008 passed, 7 skipped, 1526 subtests).
- .venv/bin/python -m unittest discover -s tests → PASS (2015 tests, 7 skipped).
- .venv/bin/python -m compileall -q mediaflow tests scripts → PASS; .venv/bin/ruff format --check . → PASS (329 files); .venv/bin/ruff check . → PASS.
- python3 scripts/check_governance.py → PASS; git diff --check → PASS.
- python3 scripts/docker_release_security_smoke_test.py → PASS against correction commit 8433319168272ecf7ccde017afc36525e8c62ea0 (“Release-security smoke acceptance passed.”); used repository-local TMPDIR for container-visible temporary resources.

### Decisions

- Kept the static route grammar aligned with the backend contract while treating the final URL segment as decoded identity data. A suffix such as .js or .bak cannot turn an accepted ID into an asset request, and the exception remains limited to one supported family and one identity segment.
- Kept failed impact reads separate from reference counts and gave read failures their own bounded copy, so transport errors cannot imply that a Save or mutation was attempted. Reread is explicit and read-only.
- The test helper models WSGI-decoded PATH_INFO; the browser proof additionally exercises encoded URLs through the actual Python HTTP/static boundary. The E2E fake follows the same exact Rules-route behavior.

### Remaining In-Slice Work

- B's reevaluation of the Slice Required Outcomes remains pending; this Developer correction addresses only the two blockers B listed for Task 41.6.
- No other in-Slice implementation work was assessed or planned in this Developer pass.

### Risks / Deviations

- The full Python unittest run emitted SQLite ResourceWarning messages and the frontend tests emitted jsdom scrollTo() notices; both suites exited successfully.
- The production build emitted the advisory that its main JavaScript chunk exceeds 500 kB (993.83 kB); the build passed.
- The Docker smoke requires repository-local TMPDIR in this environment because /tmp is not visible to the Docker daemon. The smoke harness ran unchanged and passed against the committed correction.
- config/alist.json remained ignored, absent from the commit, and unstaged. Four pre-existing untracked docs/pics/ images were left untouched and unstaged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 8433319168272ecf7ccde017afc36525e8c62ea0
```

## B Review Result

```text
Reviewed: 77f4d931bd91f9bd38b7b2ecb75ebe99f320ced7..101b9236e97b8974729653593d901b0a04249d2f
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Legal published IDs still lose the production Edit entry on refresh.**
  `mediaflow/interfaces/v2_ui.py:64-88` excludes supported identifiers by their apparent file
  suffix. This violates Task Acceptance Criteria items 1 and 3 (the existing backend identity
  contract without narrowing, and production direct-entry/refresh), Slice RO-1 and AC-3.
  Evidence: after `npm --prefix web run build`, B ran
  `python3 /tmp/mediaflow-b-review-41_6.py` against the actual Python API/static boundary, real
  temporary SQLite and legal Local roots, with no fake/intercepted API. Creating `proof.js`,
  `proof.env` and `proof.type.bak` through the Web drawer returned Save 200; each subsequent
  authenticated edit read returned 200 with the same Active object ID, and each opened successfully
  through SPA Edit. Each real browser refresh of
  `/ui-v2/rules/edit/recognitionTypes/<id>` returned **404**. These are legal current production
  objects, not requests for artifact files. Fix the exact rules-edit route using its supported
  family/depth and decoded backend ID grammar, without excluding legal suffixes. Preserve actual
  artifact allowlisting, confinement, missing-artifact failure and unknown-asset refusal outside
  that route. Correct the test that treats the legal `proof.type.bak` identity as an unknown asset;
  retain separate invalid-route/traversal/unknown-asset assertions. Cover these published IDs in
  the real-serving browser regression and keep the fake aligned with production.

- **P1 — An unsuccessful impact read is still fabricated as reference evidence.**
  `web/src/features/rules/RulesWorkspacePage.tsx:358-370` creates
  `{ total: 0, removalBlocked: true, items: [] }` for a failed impact read; lines 434-442 then tell
  the operator the object is referenced and dependencies must be repaired. This violates Task
  Acceptance Criteria item 5 (failed impact reads remain failures without invented references),
  Slice RO-5/RO-8 and AC-11. Evidence from the same real-serving browser proof: browser A loaded
  the `proof.js` inventory row; another authorized client explicitly removed this unreferenced
  object with the exact current Active authority (DELETE **200**). A then clicked the still-visible
  row's Remove button. The actual production GET `.../proof.js/impact` returned **404** with
  `error.code = not_found`, but the confirmation group displayed
  `该对象仍被 0 处引用,不能移除;必须先处理:见服务端引用证据。`.
  The browser issued zero mutation requests and current Active remained unchanged during that
  failed read. This is a reachable concurrent-management failure and sends the user to nonexistent
  dependents instead of explaining the stale inventory. Represent failed/unavailable impact
  separately from successfully read zero/nonzero references; keep deletion unavailable until valid
  current evidence exists, and offer the appropriate explicit inventory refresh or impact reread.
  Add coverage for the actual missing-object/concurrent-delete case and transport/permission read
  failures, preserving backend reference protection and no automatic mutation replay.
