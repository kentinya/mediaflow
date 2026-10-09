# Task 44.4 — Reference-aligned Rules workspace and purpose-built forms

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
current [`SLICE.md`](SLICE.md).

```text
Task ID: 44.4
Parent Slice: 44
Status: PLANNED
Task Base: 2222b6c3619631296e20db7bfaa489eb45e597e3
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Complete Slice44 RO-2 as one native Rules management journey: an operator finds the intended family
and object through the reference-aligned shared header/navigation/inventory, explicitly opens Add/
copy/Edit, corrects its purpose-built form and uses the existing object tests and one checked Save
with truthful results, retained input and publication recovery. This Task advances Slice AC9–12.

## Why This Task Exists

At this actual committed Base, `AppShell.tsx` shows an unrelated read-only Files search on Rules.
`RulesWorkspacePage.tsx` puts the Rules title below that header, uses text-button family navigation
and combines inventory title/search/filter/Add in one toolbar. `RulesObjectForm.tsx` still uses a
single-line description, checkbox enable control and generic stacking; Classification exposes
expanded rules rather than the required compact internal-rule inventory. These are the actual RO-2
structural gaps. Accepted44.3 local tests and44.2 destinations supply behavior to preserve, not an
alternative to delivering the workspace/forms. Splitting tabs, fields or styles into separate Tasks
would leave an inconsistent management journey; the entire RO-2 boundary is the next coherent unit.

### Preceding Task review and all-outcome recheck

Task44.3 source correction `bc820ce95cec3a62a48ac8859bd9175502014d71` is accepted after its first
correction. Current HEAD `2222b6c3619631296e20db7bfaa489eb45e597e3` adds only its Developer report
and is the legitimate Base of this new Task. Task44.3 Base/Goal and Slice Base were never moved.

```text
Reviewed: b6a0f49b8337f61170aac1479e8aac3b63e4675e..bc820ce95cec3a62a48ac8859bd9175502014d71
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

B inspected actual source/assertions and independently verified the five original P1 corrections
through real Python/SQLite/Local/current browser assets, including fresh-result Active-only staleness.
A separate21-case matrix covers every family's native Add/copy/Edit analysis submission; invalid
candidates/samples remain explicit errors. User-authorized default E2E repair is complete: all
original235 case coverage retained, three obsolete journeys updated one-for-one, one independent
Delete-context/Copy-context case added. No reduced permissions/assertions, hidden skips or fallback.

Independent gates: Python2312 total / 2305 passed / 7 existing skips / 0 failures; Web68 files /
1033 passed; default E2E236 passed / 0 failed / 0 skipped / 0 flaky with normal2workers; affected
E2E repeat176/176; real-Python Operations21/DirectFiles10; Rules, Storage Settings and classification
proofs; quality, example configurations, current wheel smoke and isolated Docker safety/lifecycle
PASS. Review index `/tmp/mediaflow-task44-3-r1-b-review.md`; accepted Task snapshot
`/tmp/mediaflow-task44-3-r1-pass-TASK.md`; exact command/log index
`/tmp/mediaflow-b44-3-r1-validation-results.jsonl`.

Initial B temporary probe syntax error and Developer initial172pass/4fail repeated browser run are
retained, not labelled green. The unchanged generic schema39 upgrade harness remains a limitation,
not PASS; actual schema44 wheel recovery passes. Existing7 skips, ResourceWarnings/jsdom notices
and build chunk advisory are non-blocking. Production external services are not certified.

B rechecked all outcomes: RO1/RO3/RO4 COMPLETE; RO2/RO5/RO6 INCOMPLETE. RO5's fixed52px toolbar and
RO6's regular-file-only eligibility/directory refusal remain actual gaps. Slice44 stays ACTIVE.
This Task completes RO2; no Slice closure or frozen Slice43 resumption is authorized.

## Implementation Scope

Existing shared Web shell → Rules navigation/inventories → typed family forms/drawers/Edit →
existing application/API authority and analysis behavior → integration/browser/visual evidence.
No new Domain/Persistence layer is needed for presentation. Reuse the current backend contracts.

1. Compose a Rules-specific header through the existing `AppShell`, with title at left and
   functional Rules keyword search plus existing account/notification controls at right on the
   same desktop row. Follow it with the business description and eight icon/name/description cards
   in reference order. Align shared edges; active card uses light blue/blue icon/text, others white
   with fine borders. Remove redundant headings/insets and move detailed identity diagnostics out
   of the dominant presentation without losing diagnostic access. Preserve deep links, Settings
   return, URL Back/Forward, refresh/authentication return, keyboard/current state and other pages.
2. Bind header/local search to the current family's existing keyword state/filter scope. Both
   inputs must type/clear consistently; Overview explains or disables inapplicable search. Do not
   implement cross-family search. Separate inventory title/description, then left blue Add and
   right icon-bearing keyword/state controls, then full-width table. Keep real counts, columns,
   references and backend-authorized lifecycle actions; truthful loading, empty/filtered-empty,
   partial, denied and failed states retain their dependency/access/read recovery. Navigation,
   search, refresh and row selection are read-only and never automatically open an editor/test.
3. Apply one consistent form language to all seven families in Add/copy drawers and existing
   full-page Edit: labels above controls, backend-derived required/limit hints, per-field errors,
   multiline descriptions, and accessible enable switches only where the real family supports
   enable state. Use approximately36–40px control height/20–24px field spacing as reference guides,
   preserving actual limits and all supported fields through purposeful sections/Advanced controls.
   - Recognition Types: simple ID/name/description/enable stack.
   - Type Bindings: type/four policy selectors with current references, applicable enable state and
     required identity/compatibility fields.
   - Recognition Rules: basic information, paired priority/score, output type, typed nested groups
     and explanation; preserve AND/OR/NOT, ambiguity, stop semantics and editor affordances.
   - Metadata: basics, Provider/media type, paired language/region and existing bounded request,
     candidate/timeout/retry/matching controls; preserve actual supported Provider semantics.
   - Naming: basics, actual Movie/TV directory and filename templates, missing-variable/length
     behavior, available variables; do not collapse real templates into reference examples.
   - Classification: basics and compact internal-rule list with priority, ID/name, condition
     summary, selected destination and actions. Its inner Add sits at upper right, distinct from
     outer Add. Explicit create/edit exposes all supported conditions and canonical RO3 destination
     fields; legacy conversion/readback remains explicit. Ordering must not change priority logic.
   - Organize: operation/conflict/attachment/duplicate/rollback/cleanup sections; all applicable
     high-risk permission, capability and explicitly configured fallback fields remain available.
4. Default family entry stays a full-width inventory. Only explicit Add/copy opens a right drawer;
   Edit remains full page. Use Rules-scoped classes so Files drawer styles cannot change Rules
   geometry and these fixes cannot change Files dialogs. Keep drawer title/footer visible while
   body scrolls; align Cancel then Save at right. Simple drawers may be approximately500–560px,
   complex conditions wider, narrow screens use available width. Preserve focus, keyboard operation,
   dirty-close correction and per-family draft isolation; returning restores only that family.
5. Integrate the accepted RO4 local test section into each form and preserve the separate Overview
   complete-flow entry. Retain optional definition/offline samples, relevant typed sample fields,
   exact unsaved candidate, explicit test/live intent, synthetic labels, late-response/input/Active
   freshness and retained correction/retest. RO3 canonical destinations and legacy conversion, C
   identity and old historical authority remain intact. Presentation may change; typed payloads,
   application validation, checked successor publication and no-replay behavior remain authoritative.
6. Preserve one checked Save with invalid/denied/stale/failed/unknown recovery and input retention.
   Unknown submission requires readback before another Save. Local success never authorizes Save/
   execution; no auto-publication/test/live call from navigation/render/refresh. Ordinary users
   need no CLI/raw-token transfer, redundant Validate/Activate or new confirmation ceremony.
7. Provide saved automated visual/browser evidence at1536×1024 and representative narrow760px and
   mobile390px widths using controlled temporary real configuration. Compare all six original
   images plus annotated header region together; black rectangle is annotation, sample rows/IDs/
   counts are not product data. Cover all8 sections,7family Add/copy/Edit and applicable analysis/
   recovery states, keyboard/focus/body scroll/footer, and shared-shell/non-Rules regressions.

Read and preserve the seven `docs/pics/` reference originals and hashes in SLICE.md: annotated
`整理规则需修复.png`, `识别类型.png`, `识别规则.png`, `策略绑定.png`, `元数据类型.png`,
`命名规则.png`, `分类规则.png`. Overview/Organize use their shared language without invented data.
Preserve all pre-existing untracked assets. SLICE Contract/Base, Roadmap and frozen Slice43 are
outside Developer edits. Never stage `config/alist.json`, real credentials or unrelated files.
If completing this presentation requires new schema/publication/auth/execution authority, return
the concrete dependency to B before implementing that boundary; T3 does not authorize such work.

## Acceptance Criteria

- [ ] AC1 — At1536×1024 the shared title/search/account row, description, eight navigation cards
      and aligned inventory follow the reference hierarchy. Active styling/current focus and
      supported deep-link/Back/Forward/authentication return agree; no duplicate shell/header.
- [ ] AC2 — Every inventory has separate title/description, left Add/right search-filter row and
      full-width table. Header/local keyword state and scope agree; Overview search is truthful.
      Counts/empty/partial/denied/failure states and lifecycle controls remain real and recoverable.
      Navigation/search/row selection causes no write, test or automatic editor opening.
- [ ] AC3 — All seven families expose their required purpose-built sections and complete real
      domain fields in Add/copy/Edit; description, required/hints/errors, applicable switches and
      paired controls follow Scope3. Classification has a compact internal-rule list and explicit
      inner create/edit, correct distinct Add placement and preserved destination/priority semantics.
- [ ] AC4 — Explicit Add/copy and full-page Edit preserve focus/keyboard/dirty-close/draft isolation.
      Drawer header/footer remain usable during scroll, Cancel/Save align right, simple/complex
      widths and narrow layout retain every action. Rules and Files drawer CSS are isolated.
- [ ] AC5 — Every form still tests its exact current candidate with family-relevant correctable
      input; complete flow remains a separate native Overview action. Actual results, applicable
      readiness, synthetic identity, sample/Active/late-response freshness and explicit recovery
      remain truthful. Test success grants no publication/execution or automatic live calls.
- [ ] AC6 — One checked Save publishes the complete valid successor and refreshes actual Active;
      invalid/denied/stale/failed Save keeps correctable input/known previous Active; unknown Save
      is reconciled before retry. RO3 canonical/legacy behavior, historical evidence and immutable
      object IDs survive form changes. Existing permissions/validation cannot be bypassed by styling.
- [ ] AC7 — Saved automated geometry/screenshots and a comparison matrix cover all8 sections,
      each family's applicable inventory/Add/copy/Edit/test/error states and all7 references at
      desktop/narrow sizes; keyboard/focus/scroll/action usability is demonstrated. Structural
      reference mismatches block acceptance; minor pixel differences alone do not.
- [ ] AC8 — Assigned T3 integration/quality/regression gates pass with actual commands/results;
      global header/CSS changes preserve Files/MediaLibrary/Storage/Settings/Operations/Automation
      and accepted RO1/RO3/RO4 behavior. No removed tests, weakened assertions, hidden skip/retry or
      silent fallback. Checkpoint contains only this coherent Task and preserves frozen/user files.

## Required Tests

T3 is selected because RO2 changes shared-shell integration and complete typed-form presentation,
with existing backend authority unchanged. Full Web units/default E2E are specifically required
because the shared header/CSS is reachable on every native route. Full Python, packaging and Docker
are not new mandatory T3 gates for unchanged backend/persistence/execution boundaries; Slice final
remains T4. Report actual skip/unavailable/first failure/repeat evidence, never infer a gate PASS.

From repository root:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_v2_rules_workspace tests.test_v2_rules_workspace_commands tests.test_v2_rules_workspace_previews tests.test_configuration_objects tests.test_v2_rules_object_analysis
.venv/bin/python -m unittest tests.test_classification_destination_contract tests.test_v2_storage_operations tests.test_management_setup tests.test_v2_settings_rule_readiness
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
git diff --check
```

From `web/`, extend existing focused modules and add purposeful tests for shared search/header,
all family forms, Classification compact editing, drawer geometry/state and unchanged authority:

```bash
npm run test -- --run src/shared/ui/AppShell.test.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/shared/navigation/settings-return.test.ts src/shared/navigation/destination-model.test.ts
npm run test -- --run
npm run format:check
npm run lint
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/rules-identity.spec.ts tests/e2e/rules-readiness.spec.ts
npm run test:e2e
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Default baseline236/236 now passes. Preserve coverage and normal runtime selection; update an
obsolete presentation assertion to the actual selected journey without dropping its behavior.
Test error/denied/stale/failed/unknown publication and per-family input isolation through existing
controlled API seams, retaining backend-authoritative checks and no automatic uncertain replay.
Do not reduce workers/increase timeouts/add retries/skips/ignore filters to hide a regression.

After building, from repository root run existing real-Python native proofs sequentially:

```bash
.venv/bin/python scripts/rules_identity_browser_proof.py
.venv/bin/python scripts/rules_object_analysis_browser_proof.py
.venv/bin/python scripts/classification_destination_browser_proof.py
.venv/bin/python scripts/storage_settings_browser_proof.py
.venv/bin/python scripts/rules_workspace_browser_proof.py
```

Add the last committed proof (or equivalently extend an existing committed proof and report its
exact replacement command) using production Python/API/SQLite/Local and current assets, temporary
roots and generated credentials. It must automate Scope7/AC7, explicit publication and readback,
relevant failure/recovery, exact candidate/sample and unchanged RO4 freshness; record screenshot
paths, reference-by-reference comparison and bounds for controls/header/navigation/table/drawer.
Mocks alone do not certify the complete native Rules journey. Reuse existing test seams for
controlled faults; do not remove production capabilities to manufacture a blocker. Save screenshots
outside user reference assets and inspect them, rather than treating script exit alone as visual
acceptance. No production service/media or deployment is required.

Run browser configurations sequentially or use isolated ports/artifact directories; avoid competing
full suites causing timing-only evidence. Retain the first failing run and exact corrected repeat.

## Non-goals

- RO5 long-name library toolbar repair or RO6 folder/mixed discovery; future Tasks/Slice closure.
- New recognition/matching algorithm, Metadata Provider, cross-family/global Rules search, another
  shell, schema/migration/evidence format, publication authority, Storage adapter or mutation flow.
- Removing supported form fields, weakening checked Save/RBAC, auto-test/live/publication/replay,
  fabricated reference rows/readiness, or optional wording/P2 cleanup unrelated to RO2 acceptance.
- Redesigning other pages, resuming/merging frozen Slice43, changing Contract/Base/Roadmap,
  deployment, production external-service acceptance, user reference edits or private config.

## Developer Completion Report

### Changed Files

- `web/src/shared/ui/AppShell.tsx` — Rules-specific header composition inside the one shared shell;
  shared Rules keyword-search context.
- `web/src/shared/ui/Icons.tsx` — presentation-only glyphs for the eight navigation cards.
- `web/src/shared/ui/styles.css` — Rules-scoped workspace/nav/inventory/form/drawer CSS.
- `web/src/entities/rules/rules-workspace.ts` — canonical reference-aligned family labels, card/
  inventory descriptions, per-family keyword descriptors, shared title/description.
- `web/src/features/rules/RulesWorkspacePage.tsx` — eight-card navigation, separate inventory
  title/action rows, shared keyword state, diagnostics moved out of the dominant presentation.
- `web/src/features/rules/RulesObjectForm.tsx` — one purpose-built form language across all seven
  families; compact Classification internal-rule list with explicit inner create/edit.
- `web/src/features/rules/RulesObjectDrawer.tsx` — Rules-scoped drawer classes, pinned header/footer,
  Cancel-then-Save footer order, complex-drawer width.
- `web/src/features/rules/RulesEditPage.tsx` — footer action order aligned with the drawer.
- `web/src/features/rules/RulesObjectTestPanel.tsx`, `RulesPreviewPanel.tsx` — family labels follow
  the shared set (no behavior change).
- `web/src/features/rules/rules-workspace-labels.ts` — drawer/editor labels derive from the single
  family label set.
- `web/src/features/rules/RulesWorkspacePage.test.tsx`, `AppShell.test.tsx`,
  `RulesObjectTestPanel.test.tsx`, `ClassificationDestinationForm.test.tsx`,
  `web/src/features/configuration/ConfigurationPage.test.tsx` — updated presentation assertions plus
  new reference-aligned coverage.
- `web/tests/e2e/rules-readiness.spec.ts` — updated readiness signal and three new presentation
  journeys.
- `scripts/rules_workspace_browser_proof.py` — new committed real-Python visual/geometry proof.
- `scripts/classification_destination_browser_proof.py` — opens the explicit inner rule editor and
  uses the reference-aligned family name.
- `TASK.md` — this report.

No `SLICE.md`, `docs/roadmap.md`, `docs/requirements.md`, `docs/product-experience.md`,
`docs/architecture.md`, requirement, frozen Slice 43 or user asset was edited. The four pre-existing
untracked `docs/pics/` PNGs are preserved untouched and unstaged.

### Implemented

1. **Shared Rules header.** `AppShell` composes one Rules title/description row with the functional
   Rules keyword search plus the existing notification/account controls on the same desktop row.
   The route-aware modifier is applied only to `/rules`, so the dedicated Edit route keeps its own
   subject heading and no second shell/header is created. Other routes keep their existing search
   behavior and labels.
2. **Eight reference navigation cards.** Overview plus the seven families render as icon/name/
   description cards in reference order with the light-blue/blue active treatment; each card is a
   pure navigation control (`aria-current` on the current one) that never opens an editor or writes.
3. **Inventory composition.** A separate title/description row is followed by an action row with the
   blue `+ 添加xx` at the left and icon-bearing keyword/state controls at the right, then the
   full-width table. The shared header input and the local input bind to the one family keyword
   state; the Overview disables its header input and states plainly that no global search exists.
   Counts, empty/filtered-empty/loading/denied/failure states and lifecycle actions are unchanged.
4. **One purpose-built form language.** Labels above controls, backend-derived required markers and
   limit hints, per-field errors, multiline descriptions and an accessible labelled `switch` only
   where the backend family authority reports an enable state. Every real domain field stays
   available in purposeful sections: Recognition Types (basic/state), Recognition Rules (basic,
   paired priority/score + stop-on-match, typed nested AND/OR/NOT conditions, explanation), Type
   strategy (type + four policy selectors), Metadata (Provider/media type, paired language/region,
   bounded candidate/request/matching controls), Naming (actual Movie/TV template families, variable
   list, missing-variable and length behavior), Classification (basic/state + compact internal-rule
   list), Organize (operation/conflict, explicit high-risk permission, attachments, duplicate
   detection, rollback/cleanup) — with no enable switch invented for OrganizePolicy.
5. **Compact Classification inventory.** The default state is a real table of the policy's own rules
   (priority, ID, name, condition summary, selected destination, actions). The inner `添加规则` sits
   at that list's upper right, distinct from the outer `添加分类规则`; only the explicit inner
   create/edit reveals the full supported conditions and canonical RO3 destination fields, with the
   legacy-prefix conversion still an explicit operator intent. List reordering does not rewrite the
   stored priority value.
6. **Rules-scoped drawer.** The Rules drawer no longer carries `mf-files-drawer`; it has its own
   header/body/actions with an independently scrolling body and pinned title/footer, Cancel then
   Save at the right, and a wider layout for the complex condition families. Focus, keyboard
   operation, dirty-close correction and per-family draft isolation are preserved, and Files drawers
   are untouched.

### Tests and Results

All commands run from the repository root unless a `web/` prefix is shown. Working tree contains the
Task Base plus this implementation; `web/dist` was rebuilt before the browser gates.

Python / quality:

- `PASS` `.venv/bin/python scripts/check_governance.py` → `governance check: PASS`.
- `PASS` `.venv/bin/python -m unittest tests.test_v2_rules_workspace tests.test_v2_rules_workspace_commands tests.test_v2_rules_workspace_previews tests.test_configuration_objects tests.test_v2_rules_object_analysis tests.test_classification_destination_contract tests.test_v2_storage_operations tests.test_management_setup tests.test_v2_settings_rule_readiness` → Ran 337 tests, OK.
- `PASS` `.venv/bin/ruff format --check .` → 348 files already formatted.
- `PASS` `.venv/bin/ruff check .` → All checks passed.
- `PASS` `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- `PASS` `git diff --check`.
- `FAIL / PRE-EXISTING / UNRELATED` `.venv/bin/python -m unittest discover -s tests -t .` → Ran 2312
  tests, 7 skipped, 1 failure: `tests.test_release_security.ReleaseSecurityPolicyTests.
  test_release_quality_gate_commands_are_documented_for_task_execution`. That test asserts that
  `TASK.md` contains `scripts/docker_release_security_smoke_test.py` and
  `.venv/bin/python -m unittest discover -s tests`. It reads **only** B-owned `TASK.md`, which the
  Developer never edited (the working-tree `TASK.md` is B's uncommitted Task 44.4 plan); the two
  strings are absent from B's 44.4 `Required Tests` section. Reproduced against the unmodified
  working-tree `TASK.md` alone; no Developer file is involved. Not counted as a Task PASS, and B
  decides whether B's Task text or the invariant needs the release commands. Full-run log
  `/tmp/mf-py-full.log`.

Web unit / static / build (from `web/`):

- `PASS` `npm run test -- --run src/shared/ui/AppShell.test.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/shared/navigation/settings-return.test.ts src/shared/navigation/destination-model.test.ts` → 6 files / 111 passed.
- `PASS` `npm run test -- --run` → 68 files / 1051 passed (baseline was 68 / 1033; +18 purposeful cases, no removed test, no weakened assertion, no hidden skip).
- `PASS` `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run build` (existing chunk-size advisory only).

Web E2E (from `web/`):

- `PASS` `npm run test:e2e -- tests/e2e/rules-identity.spec.ts tests/e2e/rules-readiness.spec.ts` → 17 passed (includes the three new reference-aligned journeys).
- `PASS` `npm run test:e2e` → 239 passed / 0 failed / 0 skipped / 0 flaky (default 2 workers), matching the 236 baseline plus the three new cases.
- `PASS` `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` → 21 passed on the exact repeat. First run: 20 passed / 1 failed
  (`explicit disconnect clears a lost-response batch before another principal opens the run`, an
  unrelated Operations recovery-batch timing flake); the isolated case repeated 3/3 PASS and the
  full spec repeated 21/21 PASS. Not a Rules regression and no assertion was weakened.
- `PASS` `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` → 10 passed.

Real-Python native proofs (from repository root, sequential):

- `PASS` `.venv/bin/python scripts/rules_identity_browser_proof.py` → identity journey `{"ok":true,"writes":4}`, static serving boundary OK.
- `PASS` `.venv/bin/python scripts/rules_object_analysis_browser_proof.py` → all seven families, C stays C, offline Metadata, complete-flow readiness; Active/activation/executable work unchanged.
- `PASS` `.venv/bin/python scripts/classification_destination_browser_proof.py` → legacy prefix preserved and explicitly converted, revised contract `media_library_path`; needed the explicit inner rule editor after the compact-list change.
- `PASS` `.venv/bin/python scripts/storage_settings_browser_proof.py`.
- `PASS` `.venv/bin/python scripts/rules_workspace_browser_proof.py` → new proof; 12 saved screenshots,
  reference hashes PRESERVED, all seven references `STRUCTURALLY_ALIGNED`, Active revision/digest,
  activation count and executable work unchanged, zero mutating requests.

Visual evidence and comparison matrix (saved outside user reference assets):

- Artifacts `/tmp/mediaflow-task44-4-rules-workspace-proof/`:
  `desktop-1536x1024-recognition-types.png`, `desktop-1536x1024-overview.png`,
  `desktop-1536x1024-drawer-{识别类型,识别规则,类型策略,元数据策略,命名规则,分类规则,整理策略}.png`,
  `desktop-1536x1024-classification-inner-rule.png`, `narrow-760x1024-recognition-types.png`,
  `mobile-390x844-recognition-types.png`.
- `comparison-matrix.json` (reference-by-reference assertions plus measured bounds for header,
  navigation, inventory title/Add, table, every drawer's header/body/footer, and the narrow/mobile
  viewports) and `reference-hashes.json`. The screenshots were inspected, not only script exit.

### Decisions

- The Rules header is a route-aware composition inside the existing `AppShell` rather than a second
  shell, so other routes keep their own search behavior and no duplicate header appears.
- The shared keyword state lives in the shell context and is consumed by the workspace, so header
  and local inputs cannot drift; the Overview disables the header input and explains why instead of
  advertising a global search (cross-family search stays a non-goal).
- Family display names follow the product's canonical business vocabulary and the supplied
  references (`类型策略`, `命名规则`, `分类规则`) in one shared label set used by the workspace,
  Settings readiness, drawer titles and test-panel actions; underlying families, routes, IDs and
  domain meanings are unchanged.
- The required marker is drawn with CSS on the label and exposed through `aria-required` on the
  control, so the accessible name stays exactly the field label while the requirement remains
  programmatically available.
- Classification keeps one compact internal-rule table as the default state and reveals the full
  rule editor only on explicit inner create/edit; reordering rows never rewrites the stored
  `priority` value, so presentation order cannot change priority resolution.
- The Rules drawer uses only `mf-rules-*` classes; Files/Storage drawers keep `mf-files-drawer*`, so
  neither can change the other's geometry.
- The new browser proof reuses the existing real-Python harness shape (temporary SQLite/Local roots,
  generated throwaway token, current built assets) and records measured bounds plus screenshots
  rather than asserting only exit status.

### Remaining In-Slice Work

RO-5 (long-name library toolbar repair) and RO-6 (bounded ResourceLibrary folder/mixed-selection
organization) remain incomplete; RO-1/RO-3/RO-4 behavior is preserved by this Task. No new
schema/publication/auth/execution authority was required, so no dependency was returned to B. The
Developer does not judge RO-2 acceptance or choose the next Task.

### Risks / Deviations

- `FAIL / PRE-EXISTING / UNRELATED`: the repo-level `tests.test_release_security` TASK.md
  documentation invariant fails against B's uncommitted 44.4 `TASK.md` (missing
  `scripts/docker_release_security_smoke_test.py` and `unittest discover -s tests`). Only B can
  decide whether that text belongs in the Task's Required Tests. Retained as evidence, not claimed
  PASS and not counted as an RO-2 defect.
- One Operations `continue-batch` E2E case flaked on its first full-spec run and passed 3/3 isolated
  plus 21/21 on the exact repeat; recorded rather than hidden.
- Existing 7 Python skips, jsdom/ResourceWarning notices and the Vite chunk-size advisory remain
  non-blocking and unchanged.
- Browser/visual evidence uses temporary throwaway configuration and generated credentials only;
  production external services, real media and deployment are not certified.
- The comparison matrix records structural alignment (composition, order, placement, measured
  bounds, states), not pixel-identical reproduction of the reference sample data, which the Contract
  explicitly does not require.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: ddd4bd5b82bd8d32d83cc15e57a9b0bb20cad96b
```

## B Review Result

```text
Reviewed: NOT SUBMITTED
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
