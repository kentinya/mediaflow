# Task 41.1 — Rules workspace read model and full-width inventories

This Task follows [the development workflow](../docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](../SLICE.md).

```text
Task ID: 41.1
Parent Slice: 41
Status: READY FOR B REVIEW
Task Base: 5c8aeb40fd7ea43daac100f7b205b082da921336
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Deliver the read-only entry journey for the V2 organizing-rules workspace (RO-1 and the read-only
parts of RO-7/RO-8): an authenticated operator can open `/ui-v2/rules`, understand the recognition-
to-policy relationship, and inspect every rule-family inventory from the exact immutable Active
configuration. The initial state is a complete full-width inventory with no selected object, drawer
or editor; search, filtering, tab changes and refresh remain read-only.

## Why This Task Exists

Slice 41 is active, but V2 has no Rules route, navigation destination, typed rules entity or bounded
operator projection. The existing generic configuration revision document is an implementation
surface containing unrelated sections and evidence, and is not a suitable Web contract for the
rules journey. The first independent unit must establish one server-authoritative, secret-free read
model and prove the user can enter and scan the complete rule graph before any mutation workflow is
added. This is the largest useful foundation for the later typed editors, tests/previews and
automatic Save/activation tasks.

## Implementation Scope

Domain/Application/API:

- Add a bounded read-only rules operator projection backed by the exact current Active managed
  revision. It must expose Active identity/readiness, Overview relationship data, and all eight
  sections: Type Bindings, Recognition Types, Recognition Rules, Metadata Policies, Naming Policies,
  Classification Policies and Organize Policies.
- Include stable IDs, names, bounded descriptions/summaries, enabled state and bounded reference /
  impact summaries needed by the inventories. Preserve RecognitionType identity and show binding
  references without resolving or rewriting policy identity.
- Keep the projection secret-free and digest-free for the browser. Do not return credentials,
  authorization material, raw provider options, audit payloads, Draft contents, execution authority,
  internal tokens or unrelated configuration sections. Active is the only source for the displayed
  objects; no Draft is created or read as Active.
- Expose bounded, action-oriented unavailable, empty-active, unauthorized, forbidden and malformed
  read outcomes. Reads must perform no Storage access, Provider call, Task/Job creation, Draft write,
  schedule/notification work or media mutation.

Web/API:

- Add a typed frontend API/entity boundary with strict response normalization and bounded error
  categories. Query/search/filter parameters must be allowlisted and must not make the browser
  infer or substitute policy data.
- Add `/ui-v2/rules` to the typed route/destination model and make `整理规则` the active shared-shell
  destination. Existing routes and Settings/Review recovery destinations remain unchanged.
- Implement one Rules page with an Overview and the eight required rule-family sections. Each family
  opens as a full-width searchable inventory with real Active rows, enabled/reference state and a
  clear empty/no-match state. Narrow and keyboard operation must remain complete.
- Entry, selection, search, filter, tab navigation and refresh never open a drawer or editor and
  never perform a configuration mutation. A row may be highlighted or inspected as read-only, but
  edit/create routes are explicitly deferred.
- Render distinct loading, no Active/onboarding, empty inventory, no-match, unauthorized,
  forbidden, unavailable/malformed and refresh-recovery states with a safe next action. Do not
  expose raw revision IDs/digests or protocol/exception text as ordinary workflow steps.

Tests:

- Add focused Python API/projection tests for exact-Active selection, section completeness, bounded
  redaction, references/impact, empty/unavailable/permission/malformed responses and zero side
  effects.
- Add typed entity/API tests for accepted and rejected payloads, query allowlists and error mapping.
- Add component/router/navigation tests for the route, all eight sections, default closed editor state,
  search/filter/tab/refresh read-only behavior, empty/no-match/error recovery and responsive/keyboard
  reachability.

Files/areas frozen for this Task:

- Existing managed configuration lifecycle, validation, activation, policy resolver, Strategy Test,
  Naming/Classification/Organize Preview and Settings authority remain unchanged except for the
  narrow read projection required above.
- No changes to `config/alist.json`, real credentials, supplied reference images, Storage adapters,
  OrganizerExecutor or the V1 `/ui` journey.

## Acceptance Criteria

- [ ] An authenticated operator can reach `/ui-v2/rules` from the shared shell and via a normal
      deep-link; the page is protected by the existing backend-authoritative read permission.
- [ ] The backend projection is derived from one exact Active revision, contains all eight required
      sections plus bounded Overview/identity/readiness data, and never labels Draft/candidate data
      as Active.
- [ ] Projection and frontend normalization are bounded and secret-free: no credentials, tokens,
      digests, audit contents, unrelated configuration, provider response DTOs or raw exceptions
      cross the Rules Web boundary.
- [ ] The default page is a complete full-width Overview/inventory state with no selected object,
      drawer or editor. All eight sections are discoverable and display actual Active rows or a
      truthful empty state; reference/impact and enabled state remain visible.
- [ ] Search and supported filters operate over the complete returned Active inventory, have
      deterministic no-match behavior, and do not create Drafts, call Providers, inspect Storage,
      create work or mutate configuration. Refresh only re-reads the projection.
- [ ] Loading, no Active/onboarding, empty, no-match, unauthorized, forbidden, unavailable and
      malformed states each explain the durable state and a meaningful safe next action without
      exposing implementation-detail ceremony.
- [ ] The implementation preserves RecognitionType identity, policy-binding semantics and all
      Slice safety invariants; no new mutation path or frontend authority is introduced.
- [ ] Required T3 focused, related integration and normal Web quality checks pass, and the
      checkpoint contains only this Task's coherent changes.

## Required Tests

- `python3 -m pytest -q mediaflow/tests` (or the repository's focused Python test selection covering
  the new projection and service API, plus directly affected configuration tests).
- `python3 -m compileall -q mediaflow`.
- `npm --prefix web test -- --run` with the new Rules entity/API/router/component tests and affected
  navigation/shell tests.
- `npm --prefix web run typecheck` (or the repository's equivalent typecheck script), lint and
  format checks for changed Web files.
- `python3 scripts/check_governance.py` and `git diff --check`.

External TMDB, SMB, OpenList, S3/R2 and user media are not required; use fakes, mocks, bounded local
responses and temporary roots where a read-side dependency must be exercised.

## Non-goals

- Object create/copy/edit/enable-disable/delete forms or any drawer/full-page editor.
- Page-level Save, automatic validation, checked activation, Draft recovery or Active publication.
- Recognition Strategy Test, Metadata test, Naming Preview, Classification Preview, Organize
  authority/whole-chain Preview or live Provider calls.
- Starting Scan/Preview/Organize, scheduled work, notification delivery, Storage browsing or any
  OrganizerExecutor/Storage mutation.
- New recognition fields/operators, Metadata Providers, policy semantics, frontend policy resolver,
  bulk editing, visual graph authoring, V1 retirement or unrelated shell/page redesign.
- Optional visual polish, extra sample data, P2 cleanup or test-only work outside the read journey.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_v2_rules_workspace.py`
- `web/src/entities/rules/rules-workspace.ts`
- `web/src/entities/rules/rules-workspace.test.ts`
- `web/src/features/rules/RulesWorkspacePage.tsx`
- `web/src/features/rules/RulesWorkspacePage.test.tsx`
- `web/src/routes/router.tsx`
- `web/src/shared/api/api-client.ts`
- `web/src/shared/api/rules-workspace-api.test.ts`
- `web/src/shared/navigation/destination-model.ts`
- `web/src/shared/navigation/destination-model.test.ts`
- `web/src/shared/ui/styles.css`
- `TASK.md`

### Implemented

- Added a bounded `GET /api/v1/operations/rules/inventory` projection that reads one exact managed
  Active revision, verifies integrity, exposes Active sequence/readiness/Overview and every rules
  family, and returns only allowlisted IDs, display text, enabled state, summaries and reference
  impact. The projection never returns revision IDs, digests, credentials, raw provider options,
  Drafts, audit payloads or unrelated configuration.
- Preserved RecognitionType identity explicitly in Type Binding rows: the `type-C` binding reports
  RecognitionType `C` while independently referencing Naming/Classification/Organize policy `A`.
  Search/family/enabled query inputs are strictly allowlisted and reads create no successor, Task,
  Provider call, Storage access or media/configuration mutation.
- Added the native `/ui-v2/rules` destination to the shared shell and route model. The page opens as
  a full-width Overview with no selected object, drawer or editor, and provides keyboard-operable
  tabs for Type Bindings, Recognition Types, Recognition Rules, Metadata, Naming, Classification
  and Organize policies.
- Added complete Active inventory tables with local search and enabled-state filtering, truthful
  empty/no-match states, reference/enabled visibility, responsive layout, read-only refresh and
  bounded no-Active/malformed/unavailable/permission recovery through the shared authorized-read
  boundary.
- Added backend, entity, API, route, shell and component regressions for exact-Active selection,
  redaction, section completeness, query allowlists, permission/no-Active/malformed outcomes,
  RecognitionType-C preservation, default closed editor state, search/filter/tab/refresh behavior
  and keyboard recovery.
- Correction loop (B blockers only):
  - Aligned backend and browser bounds using document-derived legal limits (`_RULES_INVENTORY_LIMITS`
    in the projection and `RULES_INVENTORY_LIMITS` in the typed entity), both derived from the
    1 MiB managed-document ceiling. A legal Active configuration with more than 512 items (for
    example 513 RecognitionTypes) now delivers every row instead of failing closed as malformed;
    both sides fail closed only past the same document-derived bound. Covered by a Python
    projection regression and an entity normalization regression.
  - Derived Overview readiness from *effective* enabled bindings and references: a binding counts
    only when it is enabled, its RecognitionType is enabled, and all four referenced policies exist
    and are enabled (skipping disabled references exactly like `RecognitionTypePolicyResolver`).
    Disabled bindings, unbound enabled types and enabled bindings pointing at disabled downstream
    policies each surface a `PARTIAL` readiness with one bounded gap per family and an actionable
    next action; `READY` is only reported when every enabled RecognitionType resolves. Covered by
    regressions for all-binding-disabled and disabled-NamingPolicy graphs.
  - Distinguished empty-family onboarding state from filtered no-match state: a family whose Active
    section is empty renders a truthful `尚无…配置` state that says reads created no Draft, while
    `没有匹配结果` remains reserved for search/status filters that matched nothing. Covered by a
    Web component regression for the empty case alongside the existing no-match case.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py` — PASS (9 tests, including the
  513-RecognitionType, disabled-binding, disabled-reference, bounded-gap and empty-family
  regressions).
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py tests/test_configuration_objects.py tests/test_management_setup.py`
  — PASS (98 tests, 96 subtests).
- `python3 -m compileall -q mediaflow` — PASS.
- `npm --prefix web test -- --run` — PASS (53 files, 774 tests) on the final correction candidate.
- `npm --prefix web test -- --run src/entities/rules/rules-workspace.test.ts src/shared/api/rules-workspace-api.test.ts src/features/rules/RulesWorkspacePage.test.tsx src/routes/router.test.tsx src/shared/navigation/destination-model.test.ts src/shared/ui/AppShell.test.tsx`
  — PASS (6 files, 42 tests) on the final correction candidate.
- `npm --prefix web run typecheck`, `npm --prefix web run lint`, and
  `npm --prefix web run format:check` — PASS.
- `.venv/bin/ruff format --check .` and `.venv/bin/ruff check .` — PASS (324 files already
  formatted; all checks passed).
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m unittest discover -s tests` — PASS (1911 tests, 7 skips) after this report
  documented the release-quality gates; the single in-range failure before that documentation fix
  was `test_release_quality_gate_commands_are_documented_for_task_execution`, which reads TASK.md
  itself and fails for any real Task that omits these commands (it passed at Task Base only because
  TASK.md there was the `NO ACTIVE IMPLEMENTATION TASK` notice; it entered the range with B's
  planning commit `78cda5e`, before this correction).
- `scripts/docker_release_security_smoke_test.py` (run as
  `TMPDIR=/root .venv/bin/python scripts/docker_release_security_smoke_test.py`) — UNAVAILABLE
  (environmental, unrelated): the harness fails while creating its own temporary Compose stack with
  `bind source path does not exist: /tmp/mediaflow-smoke-security-*/media/organized` (first attempt)
  and `.../mediaflow.json` (second attempt). The identical failure was reproduced on a clean
  checkout at the reviewed HEAD `7c1e8ac` in a separate worktree, and the Task range touches no
  Dockerfile, Compose file or script; no packaging/delivery change is claimed by this correction.
- `python3 scripts/check_governance.py` and `git diff --check` — PASS.
- External TMDB, SMB, OpenList and S3/R2 services — SKIP / not required; tests used managed local
  configuration, fakes and bounded local responses only.

### Decisions

- Active browser identity is represented by status and monotonic Active sequence/version only.
  Internal revision IDs and digests remain server-side because this read journey does not need them.
- The backend returns the complete validated rule-family sections from one captured Active revision;
  the normal page fetch is unfiltered and the browser performs read-only search/filtering over that
  complete result. The same endpoint accepts only the documented bounded filters for API clients.
- Reference impact is computed from RecognitionRule outputs and RecognitionTypePolicy references;
  bindings expose referenced policy IDs without resolving, substituting or rewriting their
  RecognitionType identity.
- Bounded rules inventory limits are derived from the 1 MiB canonical document maximum and enforced
  identically in Python and TypeScript (`RULES_INVENTORY_LIMITS`), allowing legal configs (e.g. 513
  items) to load completely while preserving defense-in-depth against malformed payloads.
- Overview readiness checks that configured RecognitionTypes have effective enabled bindings before
  declaring `READY`; empty families or disabled bindings surface actionable gaps.
- Existing shared authentication/RBAC, route continuation and authorized-read recovery remain the
  only frontend authority boundaries; no new client-side policy resolver or mutation command was
  introduced.

### Remaining In-Slice Work

- Slice 41 still requires the explicitly deferred mutation/editor journey, automatic checked
  Save/validation/activation, object lifecycle/reference-safe changes, and exact-revision
  tests/previews defined by later in-Slice work. This Task does not plan or implement those units.

### Risks / Deviations

- The correction loop produced two code checkpoints after the reviewed Head, both limited to B's
  blockers: `766fa05` (bounds alignment, truthful readiness derivation and distinct empty-family
  state) and `df8ea42` (effective binding/reference readiness with bounded per-family gaps). No
  reviewed or rejected history was amended or rewritten.
- The full Python regression exposed one in-range documentation-policy failure
  (`test_release_quality_gate_commands_are_documented_for_task_execution`): it reads TASK.md and
  requires a real Task to list the release-quality gate commands. The failure entered with B's
  planning commit `78cda5e`, not with this correction; it is fixed here by running and documenting
  those exact gates rather than by weakening the assertion.
- `scripts/docker_release_security_smoke_test.py` remains UNAVAILABLE for this environment: its own
  temporary Compose stack fails on missing bind-source paths, reproduced identically on a clean
  checkout of the reviewed HEAD in a separate worktree, with no Dockerfile/Compose/script change in
  this Task's range. No packaging or release-security claim is made by this correction.
- The first format checks found newly added Python/TypeScript files needing the repository formatters;
  they were formatted and all applicable final quality checks were rerun successfully.
- The complete Web suite emits the repository's existing jsdom `scrollTo` diagnostics; all tests
  passed and this Task did not change that test-environment behavior.
- The four pre-existing untracked `docs/pics/*.png` files were preserved untouched and excluded from
  both the implementation checkpoint and this report. `config/alist.json` remains ignored and was
  not staged or read.
- No production credentials, external accounts, real media or Storage mutations were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: df8ea424e333e0526a7b6c7422b14a7a7b8c51f6
```

## B Review Result

```text
Reviewed: 5c8aeb40fd7ea43daac100f7b205b082da921336..1b30e71240e15afd7a0076b97f6347534fe0d651
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The complete Active inventory can become unusable for a legal configuration. A temporary managed
  configuration with 513 RecognitionTypes passed import, validation and activation; the production
  projection returned all 513 rows, while `normalizeRulesWorkspace` rejects any section longer than
  512. An administrator opening `/ui-v2/rules` would see a malformed-response error instead of the
  required complete inventory (Task Acceptance Criteria 3–4; Slice RO-1). Align the backend and
  browser bounds with legal Active configuration, using a complete bounded delivery strategy if
  needed, and cover this case in the affected tests.
- The displayed readiness is false for a legal Active graph. With every RecognitionTypePolicy
  binding disabled, the managed document passed validation and activation; the projection returned
  `readiness.state = READY`, `enabledCounts.typeBindings = 0` and no gaps. An administrator entering
  Overview is told the rules are ready even though no type has an enabled downstream binding (Task
  Acceptance Criteria 2 and 6; Slice RO-1, RO-4 and RO-8). Derive readiness and next actions from
  effective enabled bindings/references and the existing capability semantics, and add a regression
  for this valid partial configuration.
- Empty Active inventories are presented as search failures. A legal validated and activated
  document with all seven rule-family arrays empty returns `available = true`, `readiness.state =
  EMPTY` and empty sections. On any family tab, `Inventory` always renders “没有匹配结果” and tells the
  operator to adjust search/status filters, even with no filter in use. This hides the actual
  onboarding state and gives the wrong recovery action (Task Acceptance Criteria 4 and 6; Slice
  RO-1 and RO-8). Render a distinct empty-family state with truthful next action while preserving
  the separate no-match state for filtered results; cover both in the Web tests.
