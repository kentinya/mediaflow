# Task 44.4 — Reference-aligned Rules workspace and purpose-built forms

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
current [`SLICE.md`](SLICE.md).

```text
Task ID: 44.4
Parent Slice: 44
Status: FIX REQUIRED
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

Correction round 1 (B Decision FIX REQUIRED, Next SAME TASK FIX LOOP). Task ID, Task Base, Goal and
Implementation Scope are unchanged; only the three listed P1 blockers and their direct root causes
were corrected.

- `web/src/shared/ui/AppShell.tsx` — one Rules title row (title + functional keyword search +
  existing notification/account controls) with the business description as a separate full-width
  line below it; other routes keep their existing top bar.
- `web/src/shared/ui/styles.css` — Rules header row/description composition; `.mf-rules-field
  .mf-rules-switch input` override that restores the real 44x24 track; section-wide label selector
  now excludes `.mf-rules-switch` and `.mf-rules-field-label`; refusal-summary and row-marker CSS.
- `web/src/features/rules/RulesWorkspacePage.tsx` — family navigation follows the header directly;
  the identity/refresh/Settings utility line moved below the navigation so it no longer interrupts
  the reference hierarchy.
- `web/src/features/rules/RulesObjectForm.tsx` — `mf-rules-field-label` class on the `Field` label;
  Classification compact list now exposes the retained per-rule errors, marks the affected row and
  offers a `修正` route that reopens the editor and focuses the exact refused control; shared
  `ruleFieldLabel` helper.
- `web/src/features/rules/RulesObjectDrawer.tsx`, `RulesEditPage.tsx` — explicit refused-Save
  summary (`保存未生效…Active 没有发生任何变化`) with the human-readable affected field, retiring
  when the described input is corrected.
- `web/src/shared/ui/rules-form-styles.test.ts` — new structural CSS guard for the two selector
  conflicts (track/thumb geometry, label exclusions).
- `web/src/features/rules/RulesWorkspacePage.test.tsx`, `RulesEditPage.test.tsx` — refusal and
  correction coverage for Add, copy and full-page Edit.
- `web/tests/e2e/rules-readiness.spec.ts` — measured header row/description/navigation hierarchy.
- `scripts/rules_workspace_browser_proof.py` — real-browser measurement of the header
  relationships, switch track/thumb, required-marker row and the refused-Save recovery journey,
  plus a saved refusal screenshot.
- `TASK.md` — this report.

No `SLICE.md`, `docs/roadmap.md`, requirements, architecture, product-experience, frozen Slice 43 or
user asset was edited. The four pre-existing untracked `docs/pics/` PNGs are preserved untouched and
unstaged; `config/alist.json` remains ignored/untracked/unstaged.

### Implemented

1. **P1 — header row hierarchy.** `AppShell` renders the Rules title, the functional keyword search
   and the existing notification/account controls as one flex row, then the business description as
   a separate full-width line. The identity/refresh/Settings utility line moved below family
   navigation. Measured at 1536x1024: the description sits below the whole title row, spans the
   header width and stays one 20px line; navigation begins directly after the header with no
   intervening dominant row. Other routes keep their existing search behaviour.
2. **P1 — form CSS structure.** `.mf-rules-field .mf-rules-switch input` ties on specificity with
   `.mf-rules-field input[type="checkbox"]` and wins by source order, so the real track is 44x24 and
   contains its 18px thumb in both states with the state text on the same row. The section-wide
   label selector now excludes `.mf-rules-switch` and the new `.mf-rules-field-label`, so the
   required `*` stays inline on its own field label. Both are asserted in the real browser and
   guarded structurally.
3. **P1 — refused-Save recovery.** A local validation refusal is now explicit everywhere. On the
   Classification compact list the affected rule is named with its retained message, the row is
   marked `待修正`, and `修正` reopens that rule's editor and focuses the exact refused control. The
   drawer and full-page Edit show a shared summary naming each affected field in business language.
   A refused Save sends no mutating request; correcting the input retires the summary.

### Tests and Results

All commands from the repository root unless a `web/` prefix is shown. `web/dist` was rebuilt before
the browser gates. Working tree contains the Task Base plus this correction.

Python / quality:

- `PASS` `.venv/bin/python scripts/check_governance.py` → `governance check: PASS`.
- `PASS` `.venv/bin/python -m unittest tests.test_v2_rules_workspace tests.test_v2_rules_workspace_commands tests.test_v2_rules_workspace_previews tests.test_configuration_objects tests.test_v2_rules_object_analysis` → Ran 261 tests, OK.
- `PASS` `.venv/bin/python -m unittest tests.test_classification_destination_contract tests.test_v2_storage_operations tests.test_management_setup tests.test_v2_settings_rule_readiness` → Ran 76 tests, OK.
- `PASS` `.venv/bin/ruff format --check .` → 348 files already formatted; `ruff check .` → All checks passed; `compileall -q mediaflow tests scripts`; `git diff --check`.
- `FAIL / PRE-EXISTING / UNRELATED` `.venv/bin/python -m unittest discover -s tests -t .` → Ran 2312 tests, 7 skipped, 1 failure: `tests.test_v2_rules_workspace_commands.RulesWorkspaceCommandTests.test_simultaneous_saves_never_publish_a_mixed_or_lost_successor` (`['rules_destination_check_failed']`). Both that test file and its production source (`mediaflow/application/configuration_objects.py`) are byte-identical to Task Base `2222b6c` (`git diff 2222b6c -- …` is empty) and this correction changes no Python source. The race is timing-dependent: it passed 5/5 isolated, 3/3 module repeats and in the focused 261-test run, and reproduced 2/12 at Task Base `2222b6c` itself in a throwaway worktree under CPU load, using the same command. Full-run log `/tmp/mf-py-full-correction.log`. Not counted as a Task PASS; B decides.
- `PASS` `.venv/bin/python -m unittest tests.test_release_security.ReleaseSecurityPolicyTests.test_release_quality_gate_commands_are_documented_for_task_execution` → OK (1 test).

Web unit / static / build (from `web/`):

- `PASS` `npm run test -- --run src/shared/ui/AppShell.test.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/shared/navigation/settings-return.test.ts src/shared/navigation/destination-model.test.ts src/shared/ui/rules-form-styles.test.ts` → 7 files / 117 passed.
- `PASS` `npm run test -- --run` → 69 files / 1057 passed (baseline 68/1033; +2 files, +24 cases: structural CSS guard, refusal/correction coverage, measured presentation).
- `PASS` `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run build` (existing chunk-size advisory only).

Web E2E (from `web/`):

- `PASS` `npm run test:e2e -- tests/e2e/rules-identity.spec.ts tests/e2e/rules-readiness.spec.ts` → 17 passed (then 13 passed on the readiness spec alone after extending its hierarchy assertions).
- `PASS` `npm run test:e2e` → 239 passed / 0 failed / 0 skipped / 0 flaky (default 2 workers).
- `PASS` `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` → 21 passed.
- `PASS` `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` → 10 passed.

Real-Python native proofs (from the repository root, sequential):

- `PASS` `.venv/bin/python scripts/rules_identity_browser_proof.py` → identity journey `{"ok":true,"writes":4}`, static serving boundary OK.
- `PASS` `.venv/bin/python scripts/rules_object_analysis_browser_proof.py` → all seven families, C stays C, offline Metadata, complete-flow readiness; Active/activation/executable work unchanged.
- `PASS` `.venv/bin/python scripts/classification_destination_browser_proof.py`.
- `PASS` `.venv/bin/python scripts/storage_settings_browser_proof.py`.
- `PASS` `.venv/bin/python scripts/rules_workspace_browser_proof.py` → 13 saved screenshots, reference hashes PRESERVED, all seven references `STRUCTURALLY_ALIGNED`, zero mutating requests. It now measures the header title/search/account row, the description line below it and its width and height, the navigation-to-header relationship, each family's switch track/thumb and state-text row, the required-marker row, and the full refused-Save recovery including the focused retained input.

Visual evidence (saved outside user reference assets), `/tmp/mediaflow-task44-4-rules-workspace-proof/`: `desktop-1536x1024-recognition-types.png`, `desktop-1536x1024-overview.png`, `desktop-1536x1024-drawer-{识别类型,识别规则,类型策略,元数据策略,命名规则,分类规则,整理策略}.png`, `desktop-1536x1024-classification-inner-rule.png`, `desktop-1536x1024-classification-refused-save.png`, `narrow-760x1024-recognition-types.png`, `mobile-390x844-recognition-types.png`, plus `comparison-matrix.json`, `evidence.json` and `reference-hashes.json`. Screenshots were inspected: the header now matches the reference hierarchy, the switch renders as a labelled track and the required markers stay inline, and the refusal names the closed rule with its correction action.

### Decisions

- The Rules header keeps one title row plus a separate description line inside the existing `AppShell`, so the search/account controls align against the title row and no second shell appears.
- The identity/refresh/Settings utility line moved below family navigation rather than being removed, preserving diagnostic access and the explicit Active refresh while restoring the reference order.
- The switch is fixed by tying specificity on the same scoped selector and relying on source order, and the label by excluding the two label kinds the section-wide rule must not own, instead of `!important` or deleting the base rules.
- The refused-Save summary names fields in business language (`分类规则 1 · 相对路径`) through one shared `ruleFieldLabel` helper, so the message and the form cannot disagree about what to correct.
- A correction retires the refusal summary for the input it described, so a stale "nothing was saved" banner cannot outlive the corrected value.
- The new structural CSS guard asserts the exact selector relationships that caused the defect, because jsdom does not apply the stylesheet; the real-browser dimensions remain the authority.

### Remaining In-Slice Work

RO-5 (long-name library toolbar repair) and RO-6 (bounded ResourceLibrary folder/mixed-selection organization) remain incomplete; RO-1/RO-3/RO-4 behaviour is preserved. No new schema/publication/auth/execution authority was required. The Developer does not judge RO-2 acceptance or choose the next Task.

### Risks / Deviations

- `FAIL / PRE-EXISTING / UNRELATED`: the concurrency test above is timing-dependent, byte-identical to Task Base, and reproduced at Task Base `2222b6c` under CPU load. Retained as evidence, not claimed PASS.
- The `rules_workspace_browser_proof.py` comparison matrix records structural alignment with measured bounds, not pixel-identical reproduction of the reference sample data.
- Existing 7 Python skips, jsdom/ResourceWarning notices and the Vite chunk-size advisory remain non-blocking and unchanged.
- Browser/visual evidence uses temporary throwaway configuration and generated credentials only; production external services, real media and deployment are not certified.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 810264416c55dd72ec88fa3690055857f6aa0dd9
```

## B Independent Verification

B reviewed `2222b6c3619631296e20db7bfaa489eb45e597e3..ddd4bd5b82bd8d32d83cc15e57a9b0bb20cad96b`.
Current committed HEAD `33a6497b871d566e8d5e59072bb1231e2e826745` adds only the Developer report
in `TASK.md`; production code is the reported implementation checkpoint. This is the first B
correction round for Task 44.4. Task ID, Base, Goal and Implementation Scope are retained.

Actual independent results:

- Governance; Python Ruff format/lint and compileall; Web format/lint/typecheck/build;
  implementation-range `git diff --check`: PASS.
- The nine Python modules listed in the Developer's focused command: 337 tests, PASS.
- The six required focused Web unit files: 111 tests / 6 files, PASS.
- Rules identity/readiness E2E, normal 2 workers: 17 passed, no failed/skipped cases.
- Real-Python identity, object analysis/complete flow, classification destination and Storage
  Settings proofs: PASS, with current built assets and temporary isolated configuration/media.
- Workspace proof plus B's production-browser probes: script exits successfully; seven reference
  hashes remain PRESERVED; screenshots and measured evidence nevertheless reproduce the blockers
  below. Its generated `STRUCTURALLY_ALIGNED` labels do not establish visual acceptance.
- Full Web unit attempt returned exit 143 before a totals report; B cannot certify its total or
  PASS. The focused repeat passed. Full default E2E and the two broader real-Python E2E suites
  were not independently rerun in this rejecting review; Developer totals remain reported evidence.
- Release TASK-document invariant at current HEAD: 1 test, PASS. The same text predicate passes
  against committed Task Base and implementation Task documents. The reported earlier dirty-plan
  failure is not reproduced at this checkpoint and is not used as a current blocker.
- Implementation manifest: 20 files including TASK.md; no Contract, Roadmap, real/private config
  or user-reference changes. `config/alist.json` remains ignored/untracked/unstaged; all four
  pre-existing untracked user PNGs remain preserved. No test removal, hidden skip/retry or
  weakened safety assertion was found in the actual diff.

Exact focused command logs are `/tmp/b44-4-python-focused.log`,
`/tmp/b44-4-web-unit-focused.log`, `/tmp/b44-4-e2e-focused.log` and
`/tmp/b44-4-{rules_identity_browser_proof,rules_object_analysis_browser_proof,classification_destination_browser_proof,storage_settings_browser_proof}.log`.
The full-unit interrupted run remains `/tmp/b44-4-web-unit.log`. Reproducible review probe command:
`.venv/bin/python /tmp/b44_4_review_probe.py`; measured output and screenshots are under
`/tmp/mediaflow-b44-4-browser-review/`. The first all-mode probe omitted reconnection after a full
Edit-page navigation and timed out; its log remains `/tmp/b44-4-browser-review-all-modes.log`.
After correcting that review-harness error, the same current production Add/copy/Edit journey
completed in `/tmp/b44-4-browser-review-all-modes-corrected.log`. No production capability was
removed or mocked to produce these findings.

## B Review Result

```text
Reviewed: 2222b6c3619631296e20db7bfaa489eb45e597e3..ddd4bd5b82bd8d32d83cc15e57a9b0bb20cad96b
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Collapsed Classification rules hide Save validation and its correction path.**
  In the supported native Add/copy/full-page Edit journey, `ClassificationRules` renders nested
  field errors only inside the `openRule` editor (`RulesObjectForm.tsx:1696`); `完成` removes
  that editor. Save then records issues and returns without a publication or a visible failure
  summary (`RulesObjectDrawer.tsx:193`, with the same behavior in `RulesEditPage`). Under a valid
  real-Python Active, enter an invalid relative path `..`, click `完成`, then `保存`: Add, copy
  and Edit all have zero visible alerts/field errors. Add sends zero mutating requests; reopening
  the rule exposes the retained error `相对路径只能由 1 到 32 个安全的非空名称段组成。`.
  Evidence: `b-review-probe.json`, `b-collapsed-invalid-rule-after-save.png`,
  `b-copy-collapsed-invalid-rule.png` and `b-edit-collapsed-invalid-rule.png` in the review artifact
  directory. The operator receives no explanation of why Save did nothing or which closed rule
  to correct. This violates RO-2 Failure/recovery, Slice AC11 and Task AC3/AC6.
  Keep compact default presentation, but expose the affected rule/field when Save is refused,
  with a native route to the retained correctable input; verify correction and a successful
  checked Save in Add/copy/Edit. Extend the existing real-browser recovery coverage.
- **P1 — Form CSS renders enable switches and required labels with the wrong structure.**
  Current production forms use the new `.mf-rules-switch input` rule, but the existing higher-
  specificity `.mf-rules-field input[type="checkbox"]` overrides its dimensions. The real
  RecognitionType Add switch measures **16.09 x 16.09 px**, while its 18px thumb is translated
  20px outside the track into the visible enable text. The same shared form serves other enabled
  families and copy/Edit. The new section-wide label selector at `styles.css:4630` also overrides
  the intended inline required label: its computed display is `grid`, height 45px at 20px line
  height, placing the `*` on a separate row throughout the forms. Evidence: the `formLayout`
  object in `b-review-probe.json` and the seven desktop drawer screenshots, compared with the
  preserved references. Operators see a dot with an overlapping state label and systematically
  separated required markers, rather than the selected labelled switch and reference-density
  fields. This violates RO-2 Add/copy/Edit presentation, Slice AC11/12 and Task AC3/AC7.
  Resolve the scoped CSS conflicts so the real track contains its thumb in both states, state
  text remains legible, and required markers stay with their field labels. Verify actual browser
  dimensions/visibility and keyboard operation across applicable families and narrow layouts;
  selector/role presence alone must not label a broken control structurally aligned.
- **P1 — The desktop Rules header does not deliver the selected row hierarchy.**
  `AppShell.tsx:205` places the description inside the flex title column, so search/account
  align against title plus paragraph instead of the title row. At the required 1536 x 1024
  viewport the available header is 1328px wide, but its description is confined to 660px and
  wraps to 40px at 20px line height. `RulesWorkspacePage.tsx:805` then inserts an always-visible
  diagnostic/action row before family navigation, whose top is y=173. The supplied annotated
  header and all six original references instead show title/search/account on one row,
  a separate full-width business-description line, then family navigation. Evidence:
  `headerLayout` in `b-review-probe.json`, desktop bounds in `evidence.json`, and
  `desktop-1536x1024-recognition-types.png` beside the preserved references. The native entry's
  hierarchy is structurally different from the explicitly selected RO-2 presentation; this
  violates RO-2 Shared header/navigation, Slice AC9/12 and Task AC1/AC7.
  Compose those rows in the existing shared shell and retain diagnostics/refresh/Settings access
  without an intervening dominant row. Preserve functional shared search and other routes;
  update the browser comparison to measure the actual title/control/description/navigation
  relationships instead of certifying alignment from element existence and a loose tolerance.
