# Task 41.5 — Rules readiness and Settings handoff

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 41.5
Parent Slice: 41
Status: READY FOR B REVIEW
Task Base: a670f9ea8c2456e24c3203d5be7d0dfb6b0f593e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An administrator can move between exact Active rule-family readiness and Settings without losing
location or mistaking stale/failed state for Active. Family URLs survive refresh, Overview gaps lead
to the affected inventory, and Settings provides a safe route back to the originating rules location.
This completes the cross-surface parts of RO-1, RO-7 and RO-8 and the required Settings handoff.

## Why This Task Exists

Task 41.4 passed its exact-revision preview acceptance. The remaining journey gap is connected:
`RulesWorkspacePage` stores its selected section only in component state, Overview readiness gaps
have no family action, and `ConfigurationPage` displays command readiness without a route to the
affected rule family. The existing Rules-to-Settings link carries no return context. Thus an
administrator cannot bookmark or refresh a family, follow a rule gap from Settings, or safely return
to the rule location after setup. These are one read-only cross-surface navigation/readiness unit,
not separate tasks for links, labels or tests. Four Task 41.4 correction rounds were reviewed; this
Task stays on the existing authority and navigation boundaries rather than adding another rules
engine or configuration lifecycle.

## Implementation Scope

- Use a bounded, allowlisted Rules section in the V2 route/search state. Default `/ui-v2/rules`
  remains a read-only Overview; a valid family deep link opens its complete full-width inventory
  with no selected object or editor. Tab navigation, refresh and browser Back/Forward preserve the
  intended section. Invalid or malformed section input falls back safely without a configuration
  write. Keep the create drawer exclusive to an explicit `添加xx` action and protect correctable
  unsaved input when navigation would leave its editing context.
- Turn actual backend Overview readiness gaps into direct actions for their affected family. Give
  empty/partial Active a dependency-aware path through the available families using existing
  readiness data; do not generate default business objects or present examples as Active truth.
- Make Settings show rule readiness derived from the same backend Active authority, with links to
  affected family inventories. Handle no Active, unavailable/malformed authority, denied reads and
  a concurrent Active change without displaying mixed-snapshot readiness as current. On an
  independently successful rule Save, a subsequent Settings visit/refresh must show the new Active
  readiness; failed Save and recoverable candidates must remain distinct from Active.
- Extend the existing allowlisted Settings return context for Rules, including an optional validated
  family section. Rules-to-Settings handoff carries the originating section; Settings offers an
  explicit safe return and retains its established post-activation return behavior. No arbitrary
  URL, raw revision/digest, secret or token enters this navigation state.
- Reuse existing authenticated Rules inventory and configuration-status/application behavior.
  Add a narrow backend projection only if necessary to prove exact Active consistency; no frontend
  rule resolver or second Active authority. Add focused Web/API and browser journey coverage for
  empty setup, affected-family navigation, publication refresh and failure/recovery.

Frozen boundaries: rule/policy object editing, preview engines, OrganizerExecutor, Storage mutation,
Scan/Task/Job execution, V1 retirement, unrelated Settings fields/pages, and all reference images.
Do not edit `config/alist.json`.

## Acceptance Criteria

- [ ] Every valid Rules family URL opens its own full-width, read-only inventory on direct visit and
      refresh; tabs and Back/Forward preserve the section. Entry, row selection, search, filter and
      tab changes do not open a drawer, mount an editor or create a Draft/work. Invalid section
      input is bounded and safely resolved. Unsaved create/edit input is preserved or warned before
      a location change that would discard it.
- [ ] Overview's actual readiness gaps provide actionable, accessible links to the affected family;
      empty/partial Active guidance follows real dependencies and never invents objects or Active
      readiness. Narrow and keyboard operation remain complete.
- [ ] Settings reports rule-family readiness for the exact current Active snapshot and links to the
      affected family. A successful publication becomes visible after refresh/navigation; failed or
      unavailable states do not claim the candidate or stale data is Active. No Active, 401/403,
      malformed response and concurrent refresh each show a bounded next action.
- [ ] Rules-to-Settings-to-Rules returns to the originating allowlisted family, including after
      first-Active setup/activation. Direct Settings access also offers a discoverable Rules route.
      Forged/oversized return state cannot cause an external redirect or expose internal tokens.
- [ ] API and Web continue to share backend permission, Active identity and validation authority;
      these reads/navigation perform no Provider, Storage, Task, Job, notification or configuration
      mutation. Existing V1 and other Settings return destinations still work.
- [ ] Focused integration/browser journeys plus T4 full regression and quality/safety gates pass;
      any unavailable external gate is reported precisely, and the checkpoint contains only this
      Task's files.

## Required Tests

- `npm --prefix web test -- --run src/features/rules/RulesWorkspacePage.test.tsx src/features/configuration/ConfigurationPage.test.tsx src/shared/navigation/settings-return.test.ts` plus any added route/API model tests.
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py tests/test_configuration_status.py tests/test_configuration_management.py` plus any new backend projection tests if backend code changes.
- Add a deterministic V2 browser journey named for this workspace, then run
  `npm --prefix web run test:e2e -- --grep 'rules workspace|rules readiness'` and report the actual
  test count. Cover no-Active handoff/return, family deep link, and post-Save readiness without
  production Providers, credentials or user media.
- `npm --prefix web test -- --run`, `npm --prefix web run typecheck`,
  `npm --prefix web run lint`, `npm --prefix web run format:check`, and
  `npm --prefix web run build`.
- `.venv/bin/python -m unittest discover -s tests`,
  `.venv/bin/python -m compileall -q mediaflow tests scripts`,
  `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`,
  `python3 scripts/check_governance.py`, and `git diff --check`.
- `python3 scripts/docker_release_security_smoke_test.py` and Base..Head scope/private-file audit;
  run the resource-heavy full gates serially and report skips/unavailability honestly.

## Non-goals

- New rule/policy fields, backend rule resolution semantics, preview logic or a second Active cache.
- New configuration lifecycle, Provider integration, Storage/Organizer execution, raw JSON journey,
  V1 retirement or unrelated page redesign.
- Optional visual polish, fixture counts, screenshot copying or tests with no user-facing journey.

## Developer Completion Report

### Changed Files

Rules workspace and shared navigation:

- `web/src/entities/rules/rules-workspace.ts` — added `isRuleFamily`, the single
  `RULE_FAMILY_LABELS` set, `RULE_FAMILY_ONBOARDING_ORDER` and
  `RULE_FAMILY_DEPENDENCY_GUIDANCE` (moved out of the page).
- `web/src/entities/rules/rules-readiness.ts` (new) — strict normalizer for the bounded Settings
  rule-readiness document; an unrecognized document throws instead of rendering zero counts.
- `web/src/entities/rules/rules-readiness.test.ts` (new) — READY/PARTIAL/EMPTY/NO_ACTIVE/
  UNAVAILABLE/MALFORMED acceptance and rejection cases.
- `web/src/features/rules/RulesWorkspacePage.tsx` — the open section is now URL search state
  (`readRulesSection`/`rulesSectionSearch`), Overview readiness gaps and family summary entries are
  real links, and an empty/partial Active gets a dependency-ordered path.
- `web/src/features/rules/RulesWorkspacePage.test.tsx` — deep link, Back/Forward, refresh, malformed
  fallback, gap action, dependency path, correctable-input and keyboard coverage.
- `web/src/features/rules/RulesObjectDrawer.tsx` — the warning's `放弃并关闭` now actually forgets the
  correctable draft (it previously called the plain close, so the input reappeared).
- `web/src/features/rules/RulesEditPage.tsx` — the return link carries the originating family.
- `web/src/features/rules/rules-workspace-labels.ts` — re-exports `RULE_FAMILY_LABELS` from the entity.

Settings and the return contract:

- `web/src/features/configuration/ConfigurationPage.tsx` — `RuleReadinessPanel` from the same backend
  Active authority, with per-family and per-gap links, an explicit non-automatic return banner, and
  `ruleReadiness` normalization (a malformed document becomes an explicit unavailable state).
- `web/src/features/configuration/ConfigurationPage.test.tsx` — readiness, unavailable-state, mixed
  snapshot, malformed document, safe-return and open-redirect-refusal coverage.
- `web/src/shared/navigation/settings-return.ts` — `rules` target with one optional validated
  `section`; a rules context carrying a path, identity or unknown family is rejected as a whole.
- `web/src/shared/navigation/settings-return.test.ts`, `destination-model.ts`,
  `destination-model.test.ts` — rules search allowlist plus unsafe-state rejection coverage.
- `web/src/shared/api/configuration-api.ts` — `ruleReadiness` typed as `unknown` until normalized.

Backend projection:

- `mediaflow/interfaces/service_api.py` — `_rule_readiness_document` reduces the existing
  `active_rules_workspace` read to bounded counts/state/gaps plus the identity of the Active this
  same status read reported. No new resolver, cache or write path. *(Correction round 1
  replaces this with the bound single-read projection; see below.)*
- `tests/test_v2_settings_rule_readiness.py` (new) — cross-surface equality with the inventory
  read, boundedness/secret-free assertions, denied reads, no-Active, an unreadable Active, a later
  activation, and the shared browser fixture contract.

Correction round 1 (B-review blocker fix, checkpoint `aa73be0`):

- `mediaflow/application/configuration_objects.py` — the workspace read model is now derived by one
  single-read projection (`_rules_workspace_from_active`) that takes the already-read Active
  revision object; `active_rules_workspace` keeps its Task 41.1 contract (no revisionId on the
  wire) by stripping the internal identity, and a new `active_rule_readiness()` returns the exact
  same read's identity together with its counts/state/gaps. The unavailable/no-active/malformed
  distinction is preserved exactly.
- `mediaflow/interfaces/service_api.py` — `_rule_readiness_document` consumes that bound
  projection directly instead of stamping the status read's identity onto a second Active read;
  the now-unused bounded-counts helper is removed.
- `web/src/features/configuration/ConfigurationPage.tsx` — `RuleReadinessPanel` treats the reverse
  interleavings as mixed too and hides the stale counts and gaps whenever the two identities in one
  status document disagree, showing only the explicit refresh-required state.
- `tests/test_v2_settings_rule_readiness.py` — a regression reproduces the exact B-review timing
  through the real SQLite managed configuration and production `MediaFlowApi`: a legal successor
  revision is published between the status document's Active read and the readiness projection's
  Active read.
- `web/src/features/configuration/ConfigurationPage.test.tsx` — covers stale counts/gaps hidden
  under the mixed state and the reverse identity mismatch.

Browser journey:

- `web/tests/e2e/rules-readiness.spec.ts` (new) — nine journeys: family deep link with a real
  refresh and Back/Forward, gap navigation plus malformed/credential-like input, dependency path,
  Settings readiness and links, no-Active, explicit safe return, publication observed on refresh,
  a read-only (GET-only) cross-surface journey, and a read-only principal.
- `web/tests/fixtures/rules-readiness.json` (new) — captured from the real Python API and asserted
  back against it, so the fake server and the backend cannot drift.
- `web/tests/fake-server.mjs` — serves `/api/v1/operations/rules/inventory` and
  `/api/v1/configuration/status` from that fixture, with `/__test__/reset-rules` and
  `/__test__/advance-rules-active` hooks.
- `web/tests/utils.tsx` — `renderApp` also returns the router so a test can assert real URL state.
- `web/src/shared/ui/styles.css` — gap/onboarding/readiness list styles.

### Implemented

- The open rules section is bounded route state: `/ui-v2/rules?section=<family>`. Default
  `/ui-v2/rules` stays the read-only Overview. A valid family deep link opens the complete
  full-width inventory with no selected object and no editor; tabs, refresh and Back/Forward all
  preserve the section. Anything that is not one of the seven families resolves to the Overview
  with no configuration write, and unknown or credential-like query keys are dropped by the shared
  navigation allowlist before an authentication continuation can replay them.
- The create/copy drawer remains exclusive to the explicit `添加xx` / `复制` action. Leaving a family
  closes the drawer and keeps the correctable session draft, and the workspace names the families
  that still hold unsaved input. The explicit discard now really forgets it.
- Actual backend readiness gaps are actionable links to the family the backend named, and an
  empty/partial Active gets a dependency-ordered path (type → rule → the four policies → binding).
  No default business object is generated and no example is presented as Active truth.
- Settings shows rule readiness derived from the same backend Active authority
  (`active_rules_workspace` behind `/api/v1/configuration/status`), with links to each family
  inventory and to every gap's family. No Active, unavailable/malformed authority and a denied read
  each stay distinct, and a projection whose Active identity differs from the Active of the same
  status read is reported as `Active 已变更,需要刷新` instead of being shown as current.
- Rules → Settings carries only `returnTo=rules` plus an optional validated `returnSection`;
  Settings states that it will not auto-navigate and offers the explicit safe return, retaining the
  established post-activation return for the other targets. No arbitrary URL, raw revision/digest,
  secret or token enters that navigation state.

Correction round 1 (B-review blocker):

- Settings rule readiness is now bound to one single Active read: `active_rule_readiness()`
  derives the revision identity and the counts/state/gaps from the same in-memory
  `ManagedConfigurationRevision` object, so two repository reads can never mix one revision's
  identity with another's counts. The status document keeps reporting its own Active identity; when
  the two identities inside one response disagree (a legal activation landing between the two
  reads), the page detects the mixed snapshot, shows only `Active 已变更,需要刷新`, and presents
  neither the stale counts nor the gaps as current. The reverse interleavings (readiness names an
  Active the status read missed, or vice versa) are detected the same way. The public rules
  inventory contract is unchanged — `revisionid` still never appears in that document.

### Tests and Results

Test Level `T4`; every gate below was actually executed. Commands were run serially.

Initial round (checkpoint `9021656`):

- `npm --prefix web test -- --run src/features/rules/RulesWorkspacePage.test.tsx
  src/features/configuration/ConfigurationPage.test.tsx src/shared/navigation/settings-return.test.ts`
  plus the added route/API model tests — `PASS` (7 files, 83 tests).
- `npm --prefix web test -- --run` (full unit suite) — `PASS` (55 files, 811 tests).
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py
  tests/test_configuration_status.py tests/test_configuration_management.py` plus the new backend
  projection tests — `PASS` (66 passed, 32 subtests).
- `.venv/bin/python -m unittest discover -s tests` — `PASS` (2006 tests, `OK`, 7 skipped).
- `npx playwright test tests/e2e/rules-readiness.spec.ts` (the named workspace journey: no-Active
  handoff/return, family deep link, publication refresh, failure/recovery) — `PASS` (9 tests).
- Full `npx playwright test` — 188 passed, 31 failed. The same 31 tests fail identically on the
  untouched Task Base built in a separate worktree (`a670f9e`, same 179 passed / 31 failed, and the
  failing-test sets are byte-identical), so these are `FAIL / PRE-EXISTING / UNRELATED`:
  `storage-management.spec.ts` 28 (the Storage inventory document is rejected by the client model),
  `deep-link.spec.ts` 2, `dashboard.spec.ts` 1 (both migration-placeholder expectations). No new
  failure was introduced and all nine new journey tests pass.
- `npm --prefix web run typecheck` — `PASS`; `npm --prefix web run lint` — `PASS`;
  `npm --prefix web run format:check` — `PASS`; `npm --prefix web run build` — `PASS`.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — `PASS`;
  `.venv/bin/ruff format --check .` — `PASS` (328 files); `.venv/bin/ruff check .` — `PASS`.
- `python3 scripts/check_governance.py` — `PASS`; `git diff --check` — clean.
- `python3 scripts/docker_release_security_smoke_test.py` — `PASS` ("Release-security smoke
  acceptance passed"). One earlier attempt failed with a 150 s Compose health timeout and no
  container logs; the immediate rerun passed unchanged. An initial attempt also failed with a
  bind-mount error because the harness `TMPDIR` (`/tmp`) is not visible to this Docker daemon;
  running it with `TASK`-independent `TMPDIR` inside the workspace resolved that environment issue,
  not a Task defect.
- Base..Head scope and private-file audit: `git status` shows only this Task's files plus the four
  pre-existing untracked `docs/pics/*.png`; `config/alist.json` remains ignored, untracked and
  unstaged. A credential/secret scan over the added files found only throwaway e2e token literals
  that are already part of the existing fixture vocabulary.

Correction round 1 (checkpoint `aa73be0`) — all gates re-executed:

- `.venv/bin/python -m pytest -q tests/test_v2_settings_rule_readiness.py` — `PASS` (11 tests),
  including the new `test_a_concurrent_activation_cannot_mix_identity_with_counts` regression that
  reproduces the exact B-review interleaving (a legal successor activation published between the
  status Active read and the readiness Active read) and proves the two identities in one response
  differ while the counts provably belong to the readiness identity.
- The B-review reproduction itself: re-running the interleaving against the production
  `MediaFlowApi` and SQLite managed configuration, the response now carries two visibly different
  revision identities (`status.active` = old, `ruleReadiness.active` = new) and the counts are
  asserted equal to the projection derived from the exact named revision — the mixed snapshot can
  no longer masquerade as one consistent snapshot, and the page's mixed-snapshot check fires.
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py
  tests/test_configuration_status.py tests/test_configuration_management.py` — `PASS` (47 passed,
  32 subtests); `tests/test_v2_rules_workspace.py` — `PASS` (19 tests), including the Task 41.1
  contract that `revisionid` never appears in the inventory document.
- `npm --prefix web test -- --run src/features/rules/RulesWorkspacePage.test.tsx
  src/features/configuration/ConfigurationPage.test.tsx src/shared/navigation/settings-return.test.ts`
  — `PASS` (3 files, 56 tests).
- `npm --prefix web test -- --run` (full unit suite) — `PASS` (55 files, 812 tests).
- `npm --prefix web run typecheck` — `PASS`; `npm --prefix web run lint` — `PASS`;
  `npm --prefix web run format:check` — `PASS` (after targeted Prettier on the edited page);
  `npm --prefix web run build` — `PASS` (Vite chunk-size warning only).
- `npx playwright test tests/e2e/rules-readiness.spec.ts` — `PASS` (9 tests).
- Full `npx playwright test` — 188 passed, 31 failed; the failing set is byte-identical to the
  Task-Base reproduction recorded in the initial round (storage-management 28, deep-link 2,
  dashboard 1): `FAIL / PRE-EXISTING / UNRELATED`, no new failure introduced.
- `.venv/bin/python -m unittest discover -s tests` — `PASS` (2007 tests, `OK`, 7 skipped).
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — `PASS`;
  `.venv/bin/ruff format --check .` — `PASS` (328 files); `.venv/bin/ruff check .` — `PASS`.
- `python3 scripts/check_governance.py` — `PASS`; `git diff --check` — clean.
- `python3 scripts/docker_release_security_smoke_test.py` — `PASS` ("Release-security smoke
  acceptance passed"), run with a workspace-local `TMPDIR` as recorded in the initial round.

### Decisions

- The section lives in the URL/search state rather than component state, which is what makes a deep
  link, refresh, Back/Forward and an authentication continuation agree by construction. The
  allowlist is expressed once in the entity module and reused by the page, the shared navigation
  guard and Settings, so there is no second family enumeration to drift.
- Settings readiness is a narrow projection of the *existing* `active_rules_workspace` read rather
  than a new resolver: the counts, enabled counts, state and gaps are the same values the workspace
  inventory returns, asserted equal in `test_v2_settings_rule_readiness.py`. The Active identity is
  taken from the same status document (`reported revisionId`/`revisionSequence`), which is how a
  concurrent activation becomes a visible mismatch instead of a mixed snapshot.
- The Task 41.1 rules-inventory contract deliberately excludes revision identity (an existing test
  asserts `revisionid` never appears in that document), so the identity was kept out of the
  inventory projection and sourced from the status document instead.
- Overview family entries became links rather than buttons. That keeps the entries bookmarkable and
  keyboard-activatable, and it keeps the existing row/tab read journey's queries unambiguous.
- The browser proof consumes a fixture captured from the real API and asserted back against it
  (`RulesReadinessFixtureContractTests`), following the existing
  `files-transfer-admission.json` precedent, so the fake cannot silently drift from the backend.
- Two small defects found while implementing were fixed inside this Task because they block its
  acceptance: the warning's `放弃并关闭` did not actually forget the draft, and the e2e no-write
  assertion initially read the fake's shared cross-worker mutation log instead of the page's own
  traffic.

Correction round 1 decisions:

- Chose "bind identity and counts to one single Active read" over "detect two reads and prompt
  refresh" as the primary fix. Detection alone would still publish one identity with the other
  read's counts; the bound projection removes the mixed snapshot at the source, and the identity
  comparison remains as a second, frontend-side line of defence for the legal interleave that can
  still occur between the status read and the readiness read.
- The exact revision identity stays out of the public rules-inventory HTTP contract (Task 41.1
  asserts `revisionid` never appears there) and is published only by the narrow
  `active_rule_readiness` Settings projection. Both projections derive from the same
  `_rules_workspace_from_active` single-read helper, so there is no second readiness derivation to
  drift.
- The unavailable/no-active/malformed state distinction is preserved exactly: the single-read
  helper only derives from an in-memory revision object; each caller keeps its own read/error
  mapping, so a failed repository read still yields `UNAVAILABLE` and not a false `NO_ACTIVE`.

### Remaining In-Slice Work

Not Developer-owned judgement. Within this Task's scope nothing is knowingly left unfinished; the
remaining Slice 41 Required Outcomes are B's and A's to evaluate. Optional visual polish and
screenshot copying were deliberately not done (Task non-goals).

### Risks / Deviations

- The 31 pre-existing e2e failures are reported, not fixed: they are outside this Task's scope and
  their root cause (the client model rejecting the Storage inventory document the fake serves)
  belongs to the Storage-management surface. They are reproduced identically at the Task Base.
- `_rule_readiness_document` catches broad `Exception` around one read so a broken Active cannot
  break the whole status document; the resulting state is the explicit `UNAVAILABLE` readiness with
  no counts claimed, which the added test covers.
- The Docker smoke gate needed a workspace-local `TMPDIR` in this environment; that is a harness
  detail, recorded here so a rerun is not mistaken for a regression.

Correction round 1 risks:

- The mixed-snapshot detection is identity comparison inside one status document, so it covers the
  B-review interleaving exactly; a same-revision read cannot be distinguished from a concurrent
  activation of a revision whose ID the page has never seen — but that case is impossible under
  the monotonic managed revision model (a new activation always produces a new revision ID).
- The concurrency regression drives the interleaving through a repository wrapper around the real
  `SQLiteConfigurationRepository` with a re-entrancy guard; it is deterministic but exercises the
  timing by call counting rather than wall-clock scheduling, which is the honest deterministic
  equivalent of the two-thread race B described.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: aa73be0ac5c7bf66ddbcfc89c83bc434197dae08
```

## B Review Result

```text
Reviewed: a670f9ea8c2456e24c3203d5be7d0dfb6b0f593e..90216562692ab52dd4c1bdc115d7ebf27eec6a67
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- P1 — Settings 的规则就绪数据没有绑定到它实际读取的 Active，违反本 Task 的“同一精确 Active 快照、并发变化不得显示混合就绪”和 Slice RO-7、Safety Invariant 6。`MediaFlowApi._configuration_status_document` 先读状态 Active，再通过 `active_rules_workspace()` 另读规则；`_rule_readiness_document` 却把第一次读取的 revision ID 填入第二次读取所得的数量与缺口。用当前 SQLite managed configuration、生产 `MediaFlowApi` 和合法的两次激活，在两次读之间发布含新增 RecognitionType 的版本，`GET /api/v1/configuration/status` 返回 HTTP 200：`status.active` 与 `ruleReadiness.active` 都是旧 revision ID，而 `ruleReadiness.counts.recognitionTypes` 已是新版的 4 项；页面的混合快照检查无法发现。请把身份与就绪投影绑定到同一次 Active 读取，或检测两次读取不一致并明确提示刷新；混合时不得展示数量/缺口为当前 Active。加入覆盖该合法并发时序的回归测试。
