# Task 44.3 — Object-scoped Rules testing and native complete-flow analysis

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
current [`SLICE.md`](SLICE.md).

```text
Task ID: 44.3
Parent Slice: 44
Status: PLANNED
Task Base: b6a0f49b8337f61170aac1479e8aac3b63e4675e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 44 RO-4: an operator can explicitly test the exact unsaved object in every Rules
Add/copy/Edit form with only that object's necessary inputs, understand its own result and
freshness, and separately run complete-flow analysis from Rules Overview. Local testing must not
require unrelated downstream configuration, claim untested readiness or grant publication/execution
authority. Save retains complete checked successor publication.

## Why This Task Exists

At this committed Base, `RulesPreviewPanel.tsx` uses a common broad sample form and strategy/policy
preview kinds; RecognitionType and RecognitionRule analysis goes through the configured strategy.
`RulesWorkspaceCommandService.preview_strategy` invokes the existing recognition strategy test,
whose implementation loads a complete managed runtime and resolves downstream policies. Existing
Metadata and Organize preview paths also require source/strategy context. These paths do not
implement independent type-definition, single-rule, binding and policy checks promised by RO-4.
The Rules Overview has no separately labelled complete-plan journey with RO-4's boundaries.

The next coherent unit is the whole testing journey across all seven object families plus its
separate complete-flow entry, including backend semantics, typed APIs, evidence, native forms and
recovery. Splitting it by result fields, families or test assertions would leave inconsistent
analysis/publication authority. RO-2's complete reference layout, RO-5's Files layout and RO-6's
folder discovery remain separate outcomes; this Task does not claim them complete.

### Preceding Task review

Task 44.2 source checkpoint `79862d9ebba5f3547f2e9b4e709d0d09824cf357` is accepted after one
correction; the actual current HEAD `b6a0f49b8337f61170aac1479e8aac3b63e4675e` adds only its
completion report and is this new Task's legitimate Base. Task44.1's PASS and original Base remain
unchanged. No Task/Slice Base is moved to hide a planning or review failure.

```text
Reviewed: 78cddf8b4090e8da86c6e69ffd237c67959b70c7..79862d9ebba5f3547f2e9b4e709d0d09824cf357
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

B verified the resolved classification projection P1 through real Python/SQLite/Local/Chromium
Save/Preview, checked legacy conversion, reopen and export. Actual Base-created historical rows,
revision bytes/digests, exact plans/results/admitted pins and manual authorizations survive candidate
restart; original legacy continuation, explicit revised successor targets and non-replay are proven.
Focused/integration 358 PASS; full Python 2222 PASS / 7 existing skips; final full Web 67 files /
1014 PASS; real-Python Operations21/DirectFiles10 PASS; classification browser proof, quality,
example configurations and wheel smoke PASS. Review/log/state index:
`/tmp/mediaflow-task44-2-r1-b-review.md`; accepted Task snapshot:
`/tmp/mediaflow-task44-2-r1-pass-TASK.md`.

Known non-blocking validation facts remain recorded, not promoted to new work:

- Default E2E: 203 passed / 32 failed, exactly the previously Base-proven failure list (no added or
  removed cases). Storage fake/read-shape, old placeholder/route and shared-fake Copy-after-Delete
  issues retain their actual baseline proof. No failed suite is labelled green.
- Initial full Web unit 3 timeout failures remain recorded; unchanged Base and candidate files
  each rerun39/39 PASS, and the final complete repeat passes1014/1014 without code/assertion changes.
- Docker safety and lifecycle runs FAIL at the unchanged health deadline after the /tmp bind
  namespace problem is avoided with workspace TMPDIR. B verified all158 installed Base-image
  modules match actual78cddf8, and that legitimate Base stack reproduces the same health failure.
  Current candidate post-activation Docker acceptance is not certified; failing gates are not PASS.
- The generic upgrade harness's unchanged schema39 expectation against actual schema44 is a
  carried-forward limitation. Actual legacy semantics and wheel migration/recovery are independently
  rehearsed. Production SMB/S3/TMDB endpoints are not certified; the built chunk advisory remains.

After this PASS, B rechecked every Slice outcome: RO-1 and RO-3 COMPLETE; RO-2, RO-4, RO-5 and
RO-6 INCOMPLETE. This Task advances RO-4. Slice44 stays ACTIVE; no Closure Packet is submitted.

## Implementation Scope

Production domain engines → focused application candidate analysis/evidence → existing managed
persistence where necessary → authenticated typed API → Rules Add/copy/Edit and Overview → tests.

1. Introduce or adapt one shared application boundary for exact submitted object analysis with
   bounded family-specific inputs and one exact captured configuration context. Reuse existing
   validators, Parser, condition engine, Naming and Classification semantics. Do not implement a
   browser evaluator or another organizing pipeline. Relevant references and enabled uniqueness
   remain authoritative; an independent local check must not require whole-runtime validation or
   resolve unrelated families. Other unsaved family drafts must not enter the candidate.
2. Implement all RO-4 local checks:
   - RecognitionType definition; optional bounded genuine associated-rule checks, including no
     associated rules, disabled eligibility and no fabricated selected-type match.
   - RecognitionRule: parse the exact synthetic path/context and evaluate only that submitted rule,
     with bounded expected/actual/truth evidence for conditions and nested AND/OR/NOT groups.
   - Type binding: type, enabled uniqueness and four explicit enabled policy references, without
     executing their engines or resolving a file.
   - Metadata: offline Provider reference/query/type/locale/request/matching settings validation,
     no live credential or Provider construction requirement; explicit live candidate-policy test
     using existing Provider ports and bounded input, independently of recognition/binding.
   - Naming: typed Movie/TV identity/episode/tag sample through the candidate's real templates,
     with variables and missing/unsafe value evidence, independently of other policies.
   - Classification: this candidate's internal rules and relevant typed identity/type/source context,
     match/fallback/manual/no-match evidence and the explicit referenced MediaLibrary plus safe
     path. Preserve Task 44.2's revised/legacy contracts; no Naming, Provider or Storage probe.
   - Organize: its real operations/conflicts/attachments/duplicates/rollback/cleanup/fallback and
     explicit high-risk permissions; intended effects/required capabilities only. Physical
     source/destination/conflict/execution readiness remains explicitly unchecked.
3. Use a family-specific `测试与预览` section in every applicable Add/copy/Edit state. Show tested
   object, exact sample/context, non-Active candidate, applicability, result and freshness; expose
   relevant inputs only. Keep local conclusion separate from runtime eligibility and complete-flow
   readiness. Opening, editing, navigating, refreshing and reconnecting never submit a test.
4. Add a native separate `完整流程检查` entry in Rules Overview. Reuse the complete Python chain:
   real recognition competition/ambiguity/stop → output type/binding → Metadata identity → Naming
   → Classification → complete OrganizePlan/target, with truthful missing-stage blockers. Offline
   identity is explicitly synthetic and performs no Provider calls; live testing remains explicit.
   Necessary destination observations use existing bounded read-only Storage ports. Neither flow
   admits executable work, changes Active or mutates media. Keep existing full Strategy Test/DryRun
   public behavior and capability available.
5. Bind evidence internally to purpose/object/candidate/sample/context and mark it stale on relevant
   candidate/sample/Active changes. Preserve historical strategy evidence's original scope and
   pins. Reuse existing managed evidence storage if appropriate; add only persistence needed for
   this journey. Do not create a generic job/framework or a second publication authority.
6. Preserve typed permission, stale/denied/unavailable handling, bounded secret-free errors,
   retained form/sample input, per-family draft isolation and explicit unknown-result readback.
   Local success cannot replace full successor validation, applicable exact-revision checks or
   atomic activation; failed Save keeps prior Active and correctable input. Ordinary operators
   neither copy raw revision/token/digest values nor repeat an uncertain request automatically.

### Operator journey

- Entry: each current Rules Add/copy/Edit form, and the separate Overview complete-flow action.
- Visible state: object and unsaved candidate, necessary sample/context, actual local result,
  condition/reference evidence, eligibility, readiness and freshness.
- Action: explicitly test; correct relevant input; explicitly rerun. Optionally test associated rules
  or live Metadata, or deliberately open complete-flow analysis.
- Success: the local object is explained independently; complete flow alone reports complete-plan
  readiness. Tested candidates remain non-Active until checked Save succeeds.
- Failure: relevant input/reference, denied/stale/unavailable or explicit live Provider failure
  names the issue and next action. Non-match and not applicable remain normal outcomes.
- Recovery: preserve input; correct relevant fields or refresh authority; explicitly rerun/read back
  without automatic replay or CLI fallback.

### Frozen scope

Do not change Slice Contract/Base, Roadmap, accepted historical closure records, frozen Slice 43 or
recognition selection algorithms. Preserve Task 44.1 direct-file commands and Task 44.2 destination,
conversion, checked Save, legacy pins and recovery. Files breadcrumbs/folder admission, provider
implementations, shared-shell reference redesign and unrelated pages are outside this Task. Preserve
all pre-existing untracked images; never include `config/alist.json`, real credentials or user media.

## Acceptance Criteria

- [ ] AC-1: Native Add/copy/Edit in all seven families tests the exact current unsaved object using
      only relevant inputs. Web and authenticated API share application semantics and permissions.
      No page entry, edit, navigation, read, refresh or reconnect automatically submits analysis.
- [ ] AC-2: A valid new/unbound type passes definition validation with no sample or downstream
      requirement. No associated rules is explicitly inapplicable. Optional associated tests report
      genuine matches/non-matches and disabled eligibility without forcing a type or resolving
      downstream policies; C remains C with A policies.
- [ ] AC-3: A submitted rule requiring path `电影` matches `电影/Example.Movie.2024.mkv` and does
      not match `Example.Movie.2024.mkv`; both work without a binding or downstream graph. Relevant
      parsed fields, per-condition/group expected/actual/truth evidence and actual output type are
      shown. Nested AND/OR/NOT, invalid operators/regex, missing/disabled output type and current
      unsaved edits follow the production engine. Selecting context never secretly rebases the path.
- [ ] AC-4: Binding checks only type/uniqueness/four references; offline Metadata checks its own
      settings without credentials or Provider construction; explicit live testing uses this policy;
      Naming renders typed Movie/TV samples; Classification evaluates its own rules and referenced
      MediaLibrary/path; Organize explains its own effects/permissions with physical readiness
      unchecked. Missing/invalid unrelated families do not fail any independent local test.
- [ ] AC-5: Every local offline test proves zero Provider construction/calls and zero media Storage
      I/O/probes/mutation. Relevant failures remain actionable. Results distinguish
      definition valid, matched, non-match, invalid input/configuration, technical failure and not
      applicable; runtime eligibility/readiness is separate, and untested stages never imply success.
- [ ] AC-6: Evidence purpose, object, exact candidate/sample/context and freshness are truthful.
      Relevant edits/sample/Active changes invalidate displayed currency; denied/stale/unavailable
      and unknown-result paths retain input and require explicit recovery, with no automatic replay.
      Other families' drafts and earlier tests cannot contaminate the current result.
- [ ] AC-7: The separately labelled Overview complete-flow journey produces a real complete plan
      through actual configured recognition competition and resolved policies, or shows exact
      missing-stage/graph blockers. Synthetic identity is labelled; live Metadata is explicit.
      C remains C, revised and legacy targets agree with Task 44.2, and every analysis path has zero
      mutation, no executable work and no execution/publication authority.
- [ ] AC-8: Local-pass evidence cannot satisfy complete-flow/publication/execution checks. A local
      pass followed by invalid successor Save leaves prior Active/input intact. Existing checked
      Save, permissions, stale/unknown publication recovery, full Strategy Test/DryRun and historical
      evidence/pins keep their original semantics across restart and applicable migration.
- [ ] AC-9: Assigned T4 evidence includes all focused/integration/full/quality gates, real-Python
      native browser journeys for every family and complete flow, and actual Base-era compatibility
      where evidence/persistence changes. Report exact commands/counts/skips/unavailable gates and
      actual pre-existing failure proof. No removed tests, weakened assertions, hidden skips,
      invented Provider success or mutated production data/credentials.

## Required Tests

### Focused and integration

Create focused production-engine/application/authenticated API tests for all AC-1 through AC-8 and
run their exact module names in the report, plus:

```bash
.venv/bin/python -m unittest tests.test_v2_rules_workspace tests.test_v2_rules_workspace_commands tests.test_v2_rules_workspace_previews tests.test_configuration_objects
.venv/bin/python -m unittest tests.test_media_parser tests.test_recognition tests.test_policy_mapping tests.test_metadata tests.test_naming tests.test_classification tests.test_classification_destination_contract tests.test_strategy_cli
.venv/bin/python -m unittest tests.test_configuration_naming tests.test_configuration_classification tests.test_configuration_organize tests.test_configuration_destination tests.test_configuration_destination_activation tests.test_configuration_destination_precheck tests.test_configuration_snapshot tests.test_configuration_successor_draft tests.test_runtime_strategy_configuration
.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_migration_rehearsal tests.test_release_security
```

Include Provider construction/call spies and Storage I/O spies, not merely mutation spies; missing/unrelated
invalid graph, exact unsaved Add/copy/Edit candidates, nested truth/non-match, ambiguity/competition
separately, disabled eligibility, C identity, relevant reference/input failures, explicit live fake
Provider success/failure/timeout/429, input/evidence staleness and local-pass/failed-Save isolation.
Use existing bounded semantics and fake Providers/local test servers; real credentials/services are
not prerequisites. Preserve all current production adapter capabilities in reachability tests.

### Full regression and quality/safety

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/check_governance.py
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
git diff --check
```

Forbidden-dependency audit expects no matches (rg exit 1). Inspect complete Task Base..Head scope,
secrets/private-file exclusion and frozen code; do not call failed/unavailable gates PASS.

### Web and native browser

From `web/`:

```bash
npm run test -- --run
npm run format:check
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Add focused typed API/form/test-result/freshness tests and a committed real-Python browser harness
or authenticated Python Playwright suite for all seven families in Add/copy/Edit plus Overview.
Report its exact command. Serve current built assets with real production application/SQLite/Local
configuration; use synthetic media/identities and explicit fake live Providers only. Exercise
unbound/new/disabled types, absent associations, genuine rule match/non-match, current unsaved input,
unrelated incomplete graph, local Metadata without secrets, typed naming/classification/effect
results, relevant errors, stale/denied/unavailable/unknown recovery, local-pass/failed-Save and real
complete-plan/blocker states. Assert no Provider/Storage calls offline, mutation/work/activation or
replay at the Python boundary; mocked Node API journeys alone do not satisfy this acceptance.
Also run `.venv/bin/python scripts/classification_destination_browser_proof.py` from the repo root
to preserve Task 44.2's native conversion/reopen/Preview/Save contract.

Run browser configurations sequentially or with distinct output directories. Avoid simultaneous
full unit suites, multiple browser suites and Docker health acceptance if resource contention makes
time-based results unreliable. Retain first failures and exact repeats; reproduce pre-existing
failures using actual Base code before excluding them.

### Compatibility, packaging and isolated Docker

```bash
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-task44-3-wheel
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-task44-3-wheel/mediaflow-*.whl
TMPDIR=/root/mediaflow/.git/task44-3-docker-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task44-3-security
TMPDIR=/root/mediaflow/.git/task44-3-docker-tmp .venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task44-3-lifecycle
```

Create the Task-owned temporary directory first; this path addresses the demonstrated daemon/agent
`/tmp` namespace mismatch without changing production Compose, image or smoke semantics. Use fresh
isolated projects/images, generated credentials and synthetic media, preserving the live deployment.
Record actual unavailable services honestly. For changed evidence/persistence, seed historical full
Strategy Test/DryRun/preview evidence and immutable revisions/digests/admitted pins with actual Task
Base code; candidate restart must preserve bytes, original purpose/scope/authority and readability.
New local evidence never retroactively satisfies old checks or repins admitted work. Run applicable
upgrade/migration rehearsal for any format/schema change; an invented newer fixture or a generic
schema-only smoke cannot prove legacy semantics. The unchanged generic Docker upgrade harness's
schema-39 expectation against Base schema 44 is a recorded pre-existing limitation, not a PASS.

## Non-goals

- Work outside Slice 44 RO-4, Slice closure/RESCOPE, Roadmap or accepted history changes.
- RO-2's complete reference header/navigation/inventory/drawer visual redesign, RO-5 toolbar repair,
  RO-6 folder discovery, or merging/resuming frozen Slice 43.
- A new recognition selection algorithm, Metadata Provider, storage adapter, global Rules search,
  second shell, parallel organizing engine or generic evidence/job framework.
- Weaker checked Save/activation, relaxed references for publication, automatic live tests,
  synthetic identities labelled verified, or local results authorizing execution.
- Optional wording, P2 cleanup or unrelated test-harness repair as independent work.

## Developer Completion Report

### Changed Files

Production (all under `mediaflow/`):

- `application/rules_object_analysis.py` (new) — the one shared object-scoped
  analysis boundary plus the separately labelled complete-flow check.
- `application/recognition.py` — production condition evaluation for exactly one
  submitted rule with a bounded, secret-free `ConditionTrace`/`RuleEvaluation`.
- `application/strategy_test.py` — an explicit offline `synthetic_identity` input
  for the complete-flow chain; it performs no Provider call, is labelled
  synthetic and is never reported as a verified match.
- `application/rules_workspace_commands.py` — shared `_compose_candidate_draft`
  used by Preview and the new `stage_analysis_candidate`; the Provider credential
  requirement became a publication-only gate so an offline object test needs no
  live credential.
- `application/configuration_objects.py` — shared section/kind, MetadataPolicy,
  OrganizePolicy-warning and analysis-runtime helpers.
- `infrastructure/strategy_user_configuration.py` — the runtime condition parser
  is now the single public `parse_recognition_condition`, reused by the local
  rule test so no second interpretation can exist.
- `interfaces/service_api.py` — typed authenticated `POST
  /api/v1/operations/rules/analysis/{family}` and `POST
  /api/v1/operations/rules/complete-flow`, both `MANAGE_CONFIGURATION`, strict
  envelopes, bounded secret-free errors.

Web (`web/src/`):

- `features/rules/RulesObjectTestPanel.tsx` (new) — the family-specific
  `测试与预览` panel used by every Add/copy/Edit form.
- `features/rules/RulesCompleteFlowCheck.tsx` (new) — the separately labelled
  Overview `完整流程检查` entry; it reads its authority only on explicit open.
- `features/rules/RulesEditPage.tsx`, `RulesObjectDrawer.tsx`,
  `RulesWorkspacePage.tsx`, `RulesPreviewPanel.tsx` — mount the new surfaces and
  keep the existing full-chain preview available.
- `shared/api/api-client.ts` — `runRulesObjectAnalysis`, `runRulesCompleteFlow`
  and their strict normalizers.

Tests and evidence:

- `tests/test_v2_rules_object_analysis.py` (new, 88 tests).
- `web/src/features/rules/RulesObjectTestPanel.test.tsx` (new, 15 tests).
- `scripts/rules_object_analysis_browser_proof.py` (new) — real Python-served
  SQLite/Local/Chromium journey for all seven families and complete flow.

`TASK.md` carries B's own Task 44.3 document. The four pre-existing untracked
`docs/pics/*.png` files are unrelated and deliberately unstaged; `config/alist.json`
was never touched.

### Implemented

1. **One shared application boundary.** `RulesObjectAnalysisService.analyze`
   stages exactly one submitted unsaved object as one non-Active candidate from
   one exact captured Active identity, then analyses only that family.
   `stage_analysis_candidate` reuses the same allowlists, normalization,
   reference validation and optimistic fence as Preview/Save but deliberately
   stops before whole-document validation, so an independent local check never
   needs a complete managed-runtime load or an unrelated downstream family.
2. **All seven local checks.** RecognitionType definition (with optional genuine
   associated-rule tests and explicit disabled eligibility), RecognitionRule
   single-rule evaluation with nested AND/OR/NOT traces, Type binding
   (type + enabled uniqueness + four references, no engine execution), Metadata
   (offline settings with no credential or Provider construction, plus an
   explicit live candidate-policy test), Naming (typed Movie/TV sample through
   the candidate's real templates), Classification (its own rules plus the
   referenced MediaLibrary and safe relative path, no Naming/Provider/Storage
   probe) and Organize (real effects and required capabilities with physical
   readiness explicitly `未检查`).
3. **Separate complete flow.** `complete_flow` reuses the complete Python chain
   through `strategy_runner_from_configuration(...).run_path(...)`, reports
   truthful per-stage blockers (recognition/ambiguity, binding, metadata,
   naming, classification, organize) and an explicitly labelled synthetic
   offline identity. Live Metadata stays a separate explicit choice.
4. **Native surfaces.** Every Add/copy/Edit form shows the family-specific
   `测试与预览` panel with only that family's relevant inputs; Overview shows the
   separately labelled `完整流程检查`. Opening, editing, navigating, refreshing
   and reconnecting never submit: only the explicit button does, and a relevant
   edit or Active change marks the displayed result stale.
5. **No new publication or execution authority.** Every analysis path is
   zero-mutation: no Active change, no activation, no executable Task/Job work
   and no media Storage write. Save keeps its complete checked successor
   publication, including the Provider credential gate, which is now explicitly
   publication-only.

### Tests and Results

Assigned level: **T4 (FULL / HIGH RISK)**.

Focused and integration (all PASS):

```text
.venv/bin/python -m unittest tests.test_v2_rules_workspace tests.test_v2_rules_workspace_commands tests.test_v2_rules_workspace_previews tests.test_configuration_objects tests.test_v2_rules_object_analysis
Ran 259 tests — OK
.venv/bin/python -m unittest tests.test_media_parser tests.test_recognition tests.test_policy_mapping tests.test_metadata tests.test_naming tests.test_classification tests.test_classification_destination_contract tests.test_strategy_cli
Ran 130 tests — OK
.venv/bin/python -m unittest tests.test_configuration_naming tests.test_configuration_classification tests.test_configuration_organize tests.test_configuration_destination tests.test_configuration_destination_activation tests.test_configuration_destination_precheck tests.test_configuration_snapshot tests.test_configuration_successor_draft tests.test_runtime_strategy_configuration
Ran 134 tests — OK
.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_migration_rehearsal tests.test_release_security
Ran 119 tests — OK
```

Full regression and quality/safety (all PASS):

```text
.venv/bin/python -m unittest discover -s tests   →  Ran 2310 tests — OK (skipped=7)
.venv/bin/python scripts/check_governance.py     →  governance check: PASS
.venv/bin/ruff format --check .                  →  346 files already formatted
.venv/bin/ruff check .                           →  All checks passed!
.venv/bin/python -m compileall -q mediaflow tests scripts   →  OK
.venv/bin/python -m pip check                    →  No broken requirements found.
.venv/bin/mediaflow --config config/strategy.example.json config validate        →  Configuration valid
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate →  Configuration valid
grep -rn -i -E 'ffprobe|ffmpeg' mediaflow pyproject.toml →  no matches (exit 1, as required)
git diff --check                                 →  clean
```

The seven skips are the same pre-existing skips the accepted Task 44.2 report
recorded; no test was removed, weakened or hidden.

Web and native browser (all PASS):

```text
npm run test -- --run   →  Test Files 67 passed (67); Tests 1014 passed (1014)
npm run format:check    →  PASS
npm run lint            →  PASS
npm run typecheck       →  PASS
npm run build           →  PASS (pre-existing chunk-size advisory only)
npm run test:e2e        →  203 passed / 32 failed — the exact Base-proven list
.venv/bin/python scripts/rules_object_analysis_browser_proof.py
    all seven families valid/matched with Provider=0 Storage=0
    unbound new type definition: valid / not_applicable
    RecognitionType C with A Naming/Classification policies: C
    complete flow: complete_plan_ready (blockers=[])
    Active, activation count and executable work unchanged
    browser journey: ruleMatch=电影/Example.Movie.2024.mkv,
      ruleNonMatch=Example.Movie.2024.mkv, bindingKeepsC=C,
      offlineMetadata=offline, organizePhysicalReadiness=未检查
    PASS: object-scoped rules analysis and complete flow through the real boundary
.venv/bin/python scripts/classification_destination_browser_proof.py
    PASS (Task 44.2 conversion/reopen/Preview/Save contract preserved)
```

The new harness proves safety at the Python boundary rather than only in the
browser: it reads the real configuration authority and the real SQLite runtime
database before and after every analysis and requires the Active revision,
digest, activation count and executable Task/Job work to be unchanged.

Compatibility, packaging and isolated Docker (all PASS):

```text
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-task44-3-wheel
    →  mediaflow-2.0.0.dev0-py3-none-any.whl built
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-task44-3-wheel/mediaflow-*.whl
    →  PASS (Schema 44)
TMPDIR=.git/task44-3-docker-tmp .../docker_release_security_smoke_test.py --image mediaflow:task44-3-security
    →  Release-security smoke acceptance passed.
TMPDIR=.git/task44-3-docker-tmp .../docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task44-3-lifecycle
    →  Docker transfer lifecycle acceptance passed.
```

Both Docker gates passed here, unlike the Task 44.2 record. This Task changes no
persisted evidence format, so `CONFIGURATION_SCHEMA_VERSION` stays 10 and no new
table or migration is required; the wheel smoke independently confirms schema 44.

Pre-existing non-blocking facts (recorded, not promoted, not labelled green):

- Default E2E remains 203 passed / 32 failed, the previously Base-proven list.
  No new failure was added and none was removed.
- The generic Docker upgrade harness's unchanged schema-39 expectation against
  actual schema 44 remains a carried-forward limitation.
- Production SMB/S3/TMDB endpoints are not certified; the built chunk-size
  advisory remains.

### Decisions

- **Reuse the production condition engine.** `RecognitionRuleEngine.evaluate_rule`
  emits the trace from the same comparison the pipeline uses, so the local rule
  test cannot diverge from runtime. No browser evaluator exists.
- **One candidate, one authority.** Analysis reuses Preview's composition and the
  exact-revision fence, and stops before whole-document validation. This is what
  makes an independent local check genuinely independent while still rejecting
  dangling references, duplicate enabled bindings and unsupported fields.
- **Publication-only credential gate.** RO-4 requires offline Metadata validation
  without a live credential; Save still fails closed without one. The flag is an
  explicit parameter rather than a duplicated validator.
- **Synthetic identity is bound to the resolved type.** An unpinned synthetic
  identity is bound to the type the submitted path actually resolved to, so a
  pinned RecognitionType is never silently rebound, and an earlier-stage blocker
  is reported truthfully instead of a misleading metadata failure.
- **Complete flow analyses the current Active, not a staged object.** It is the
  combined processing check, so it verifies the exact observed Active identity
  and refuses a stale one instead of silently analysing a different graph.
- **The Overview authority read is lazy.** Landing on Overview stays one
  read-only inventory request; the complete-flow authority is read only when the
  operator deliberately opens the entry.

### Remaining In-Slice Work

- RO-2's complete reference header/navigation/inventory/drawer redesign.
- RO-5's Files toolbar repair and RO-6's folder discovery.
- Slice closure remains A's decision; this Task does not claim RO-2, RO-5 or RO-6.

### Risks / Deviations

- The E2E failure list and the generic Docker upgrade schema-39 expectation are
  pre-existing and unchanged; this report does not judge whether they block PASS.
- `complete_flow` performs a whole-managed-runtime load. That is correct for the
  combined check, but it means the complete-flow entry is unavailable for a
  document that cannot be loaded at all; it then reports a truthful `graph`
  blocker rather than a fabricated plan.
- The local RecognitionType associated-rule test evaluates only the type's own
  rules and never resolves a downstream policy. A match therefore proves the
  rule's condition, not that the type is runtime-eligible; the result says so
  explicitly and runtime eligibility is a separate field.

### Checkpoint

```text
Status: NOT SUBMITTED
Head SHA: NOT SET
```

## B Review Result

```text
Reviewed: NOT SET
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
