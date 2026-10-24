# Task 43.3 — Automation Inventory, Execution Records and Truthful Statistics

Authority: committed [SLICE.md](SLICE.md), [Development Workflow](docs/development-workflow.md)
and [B experience](docs/agent-experience/task-planner-reviewer.md). Developer also reads the
[implementation experience](docs/agent-experience/developer-implementation-role.md).

```text
Task ID: 43.3
Parent Slice: 43
Status: FIX REQUIRED
Task Base: 78ec108d4473e8c140174c1356d0e88a1ae42b34
Difficulty: High
Test Level: T3
Planner / Reviewer: B — temporary role exception explicitly authorized by user, 2026-10-23
Reassessment source / Contract: 533a666860a571e61c78ac49b3e45c44acaa419e
Decision: FIX REQUIRED — candidate 87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12; implementation 29048876f0546efd3ba9c8a5cd5463b7f4b8168f; same Task/Base/Goal/Scope
Next Action: DEVELOPER CORRECTS THIS TASK; B owns corrected-candidate T3 acceptance; Slice Final stays T4
```

## Goal

An operator finds every authorized Automation definition, understands its next/latest actual state
and population statistics, reads scheduled/manual results and reasons in Automation, then follows
a prerequisite-repair link or the exact Task Center run/problem and returns to the same context.
Complete **RO-1 inventory/query/statistics**, consolidated **RO-5**, and related **RO-7 read/
navigation/failure surfaces**. RO-6 settings publication/actual resident consumption remains a
separate coherent unit; a settings link is not its completion.

Traceability: V2-AUTO-001/005/006, V2-UX-001/002/003, UX-001/002/003/005/007/010,
REQ-TASK-008, REQ-RECOVERY-002/006/009, the inventory/records portion of Slice AC-1,
AC-2/7/8/11 and this Task's evidence contribution to AC-12. Settings outcomes RO-6/AC-9/10
and the settings portion of AC-1 remain outside this Task and incomplete; AC-12's whole-Slice
T4 gate is not satisfied by this Task's T3 checks.
Follow the complete [Automation journey](docs/product-experience.md#target--complete-native-automation-workspace-active-slice43)
and [CURRENT/TARGET architecture](docs/architecture.md#automation-and-unattended-execution).

## Reassessment and preserved authority

- Recover the same ID/title/Base/Goal/Scope from
  `c539429c2c3aaeaab4842b87d3c858e77106fed1:TASK.md` (PLANNED / NOT STARTED).
  The reassessment source is **not** a new Task Base. The current submitted candidate and
  implementation checkpoint are recorded in the B review below; prior reviews remain in Git.
- Slice43 Base remains `853973dbbf8289fa2ad40657033e94e870a690e4`. Frozen Contract/branch
  `ed974e0df8b263f631bfe48b524da461013d8780:SLICE.md` /
  `frozen/slice-43-2026-10-15`, integrated preservation refs and historical43.1/43.2 reviews stay
  unchanged. Historical PASS does not certify current consumers.
- Accepted45 implementation `4fcb0028f987f8746f0a8aa7b309e360b07c598e` and closure
  `13ecfc0e75fc34ff0ae489e655124a178943cba4:SLICE.md` protect Task Center/shared analysis and
  Scan/standalone Preview/FileIndex retirement. Replace obsolete plan obligations accordingly;
  do not restore their routes, executors, schemas or dedicated migration/history compatibility.
- Apply committed RO-5/AC-8: records remain read-only; durable formal organizing-task handoff
  determines recovery ownership. Old local-control/recovery wording is superseded.
- This reassessment acts as B under explicit user authorization; no A Final Review, A-owned
  boundary/closure update or product acceptance is performed.

## Actual-code gaps and current baseline

| Actual source / entrance | Correction within this Task |
|---|---|
| `AutomationListPage.tsx`, `automation-query.ts`; `MediaFlowApi._automation_definitions_operator_page` in `mediaflow/interfaces/service_api.py` | Bounded cards and Active-first prefix lack complete server queries/paging and metrics; all authorized Active/Draft-only definitions must be reachable. |
| `_automation_definition_operator_occurrences`, `_automation_run_once_history` | Scheduled page plus up to50 discovery entries is not one admitted-run population; read/projection exceptions silently drop manual history. |
| `mediaflow/infrastructure/sqlite_runtime.py:list_definition_run_once_discoveries` | Global LIMIT precedes definition filtering; older desired records disappear. Reuse shared authoritative queries instead of browser merges. |
| Same repository `_run_query_document`, `operations_runs_window`; shared Operations API/query models | Reuse explicit deduplicated Job→Task anchors, transaction/count/cursor machinery and manual admission/origin links; add bounded definition/trigger selectors and Automation aggregates. |
| `_automation_definition_actions` versus `web/src/entities/operations/automation.ts:normalizeAutomationDefinition` | Backend omits retired `preview` action but parser requires it. Align supported read types/consumers without restoring the action/product. |
| `DefinitionScopedExecutionService.run`, shared manual execution and Task Center recovery | Formal Task exists before scan/plan. Classify by durable origins/checkpoints, not first mutation or missing Task link. |

Fresh baseline at the reassessment SHA with production Web assets built this turn:

- Governance PASS;139 focused Python tests PASS; `npm --prefix web run build` PASS.
- Original real-Python lifecycle/Run-once specs: **9 passed / 6 failed**. Three retained-history
  tests encounter the required-preview parser mismatch; corruption behavior is not yet reached.
  Two root-scope success fixtures exceed their saved5-item bound and correctly hit incomplete
  discovery refusal. Narrow success fixtures through the existing scope field; retain separate
  overflow refusal coverage and never relax the guard.
- The mixed-item test registers a Worker after reading its plan and clicks a stale disabled action.
  An ignored diagnostic copy adding existing same-page Refresh reaches execution admission, then
  fails at the old spec's removed `/__harness__/run-run-once-mixed-worker` helper (404). This is
  stale fixture/readiness evidence, **not** mixed recovery PASS. Adapt the fixture/Worker driver
  to current supported services and rerun the complete independent-sibling recovery obligation.
- These fresh findings do not claim identical attribution of the historical seven failures.
  Full current lifecycle/Run-once/recovery acceptance remains pending, not waived.

Original plan, raw logs, diagnostic input diff/config/trace and evidence index are local-only at
`.git/validation-evidence/533a666860a571e61c78ac49b3e45c44acaa419e/b-reassess43.3-20261023/`.

## Implementation Scope

### Complete operator journey

- **Entry:** shared-shell `自动化`, supported definition/occurrence deep links or Task Center return.
- **State:** `任务列表 / 执行记录 / 全局设置`; published/Draft-only and enabled/granted/ready
  distinctions; scope/schedule/limit, next/latest run, full-population cards, original results
  and separately labelled linked handling progress.
- **Action:** search/filter/sort/page/read reasons; explicitly navigate to existing configuration,
  lifecycle/shared analysis/grant/Run-once or Task Center. Records execute no recovery.
- **Success:** every authorized row is reachable, counts match declared population, and repair/
  recovery returns to definition/tab/filter/page context without resubmission.
- **Failure/recovery:** distinguish loading/empty/setup/denied/not-found/stale/malformed/unavailable;
  preserve correctable filters, explain durable state/effects and exact legal next action.
  Unknown admission/handoff requires reconciliation/investigation before another command.

### Ordered implementation steps

1. **Align existing read contracts and native fixtures.** Start from actual Automation list/detail/
   lifecycle/occurrence/Run-once routes. Remove the obsolete required-preview action dependency
   from current types/parsers/consumers and align API/Web tests. Supported historical automatic-
   organization details remain readable after rename/removal without open-Draft fallback; corrupt
   published evidence remains explicitly unavailable. Repair bounded success scopes, Worker
   readiness read order/Refresh and the mixed-recovery test driver through current real services.
   Preserve independent sibling/non-replay proof. No lifecycle/admission/Worker semantic rewrite.
2. **Build one reusable admitted-run query.** Extend shared repository/application queries and
   existing `/api/v1/operations/runs` reads with definition/manual-scheduled selectors. Resolve
   occurrence→Job→Task and manual definition origin→intent→admitted execution→Task by persisted
   identities, not time/name/current-Active guesses. A Job acquiring its Task keeps one identity/
   count; pending and admitted pre-Task failures remain visible. Filter before LIMIT, sort with
   stable ties and return bounded pages/counts with principal/query/read-basis-scoped cursors.
   Batch bounded page evidence; no unbounded Python/browser scan or new result store/queue.
3. **Project truthful records and recovery ownership.** Reuse Results/checkpoints and recovery
   relations for original outcome, start/end, per-item totals, reached bound, stage/reason, known
   effects, safe-repeatability explanation and exact next-action links. Keep discovery/preparation/
   grant attempts, rejected admissions and blocked-emission diagnostics separately labelled and
   inspectable through supported evidence; exclude them from admitted-run pagination/metrics.
   Historical name/scope/mode/version uses admission/pin, survives removal/reopen and never borrows
   today's Active. Missing/corrupt evidence cannot silently remove rows or become zero.
4. **Complete definition queries and metrics.** Extend the existing inventory read/API/client with
   bounded search, enabled/source filters, stable sort/page, counts and latest admitted manual/
   scheduled outcomes. Draft-only correction entries remain reachable/labelled and excluded from
   published/enabled counts/actions. Capture one clock and exact immutable Active revision plus
   a consistent runtime read transaction; incompatible publication/linkage yields an explicit
   stale/unavailable read for bounded refresh. Return exact metric windows/timezone/basis.
5. **Deliver native list and read-only records.** Use the original inventory composition/light
   shell and shared query/auth/error components. Table: name, enablement, ResourceLibrary/scope,
   readable schedule/timezone, limit, next run, latest result/time and backend-advertised actions.
   Records filter by definition/trigger/outcome/time and link exact Task Center run/problems.
   Preserve compatible detail/occurrence links and safe return state across reload/reconnect;
   validate return routes and principal-cache isolation. Settings tab/header shortcut reach the
   same existing managed settings surface; no duplicate form/store or RO-6 adoption claim.
6. **Verify and hand off one candidate.** Add the database/API/query/UI/native coverage below and
   inspect actual desktop/narrow renders against preserved references. Update only necessary
   factual affected guidance/contracts, leaving undelivered TARGET explicit. Freeze a coherent
   implementation checkpoint with affected-test report for B.

### Record result, handling progress and recovery boundary

- Original failed/partial/cancelled/uncertain results/reasons remain historical facts. Task Center
  recovery never changes them into successful original execution or a new scheduled trigger.
  Show later handling separately using actual linked continuation/execution evidence: unhandled,
  handling, recovery failed, resolved or investigation as justified. Admission/analysis completion
  is not resolution. Unavailable follow-up evidence is explicit; changed current Task status alone
  cannot rewrite original results or prove recovery success.
- Proven pre-start failure links prerequisite correction and the existing explicit supported
  retry/Run-once entrance. Backend evidence must prove no formal execution/effects and old attempt
  settled/fenced; command owner revalidates current permissions/exact context/pins/authority.
  Queued/claimed work is not retryable. Unsupported old-context retry explains a distinct new Run
  once or next scheduled evaluation while preserving the original record. No new retry command,
  automatic resubmission or authority shortcut is added to records.
- Durable formal organizing Task/execution handoff routes even scanning/recognition/metadata/
  planning failure before mutation to Task Center. Missing Task link alone proves nothing.
  Ambiguous handoff/unknown effects permit reconciliation/investigation only. No synthetic Task/
  Job is created for navigation. Successful/uncertain siblings retain existing non-replay rules.
- Records have no file-decision forms, plan generation, pause/resume/cancel or recovery execution.
  Reads/reason expansion/filter/page/refresh/return create no work/Draft/grant and invoke no
  Provider or Storage operation. Existing Task Center owns all execution/recovery commands.

### Metric contract

- Cards cover the **full authorized population**, independent of list/record search/filter/page;
  label that scope. Published/enabled counts use exact current Active. Removed-definition admitted
  history still contributes to run metrics.
- Month-to-date admitted run count/success rate use configured **system timezone**, separately
  from Cron/browser timezone. Compare run count with previous month's equivalent elapsed local-
  calendar period clamped to its end; return evaluation time, exact windows and basis.
- Count each original admitted run once. Terminal runs in that calendar cohort form the success
  denominator, including failed/partial/cancelled/terminal-uncertain; active/waiting are separately
  visible and excluded. Recovery attempts do not duplicate original admissions.
- Apply admitted outcome semantics/item evidence: Job completion is not organization success,
  no-work is labelled, skipped is not organized and bound reached is not exhaustion. Never relabel
  surviving removed-mode evidence as organization or add dedicated old-mode compatibility/history.
  No denominator/comparable prior count means `暂无可比数据`; unavailable/incomplete is distinct
  from zero. No frontend page-derived aggregates or percentages.

### Risk boundary

High / **T3** remains appropriate for shared read-model/API/Web integration and navigation only.
No schema/migration, persisted recovery workflow, new retry semantics, permission model,
configuration write, admission/execution change or Worker ownership change is authorized here.
If existing evidence cannot meet an outcome without such changes, stop dependent implementation
and return to B for explicit same-Task risk/plan reassessment and T4 where required; do not weaken
the outcome or silently expand T3. Independent authorized work may continue. Slice Final stays
**T4**. Preserve accepted45, exact pins, OrganizerExecutor mutation authority, Storage confinement,
redaction, fences, C-with-A/A identity and non-replay.

## Acceptance Criteria

- [ ] **T1:** Native inventory/records complete across pages, empty/setup/error/denied/loading,
  keyboard/narrow use, refresh-safe deep links and bounded return context.
- [ ] **T2:** Server query/sort/page reaches every authorized definition/Draft-only correction;
  no hidden prefix or Draft-as-Active action/count. Current supported lifecycle/shared analysis/
  grant/Run-once navigation survives read-contract alignment.
- [ ] **T3:** Combined manual/scheduled admitted history retains stable deduplicated identities,
  filter-scoped totals and historical context through Task linkage, rename/remove/reopen;
  pre-Task failures remain visible and preparation/blocked/rejected evidence stays distinct.
- [ ] **T4:** Full-population metrics satisfy calendar/cohort/denominator rules across pages,
  filters/months/timezones; unavailable query/evidence never becomes empty/zero.
- [ ] **T5:** Records retain original results/reasons/effects and separately linked handling
  outcomes. Verified recovery updates handling only; successful/uncertain siblings never replay
  and recovery is not a second scheduled trigger or successful original execution.
- [ ] **T6:** Proven settled pre-start failure guides repair/supported explicit command; queued/
  claimed/ambiguous work cannot offer start-again retry. Formal Task failures before mutation link
  Task Center. Records execute no control/recovery/re-analysis command.
- [ ] **T7:** Compatible page/count/metric/latest read bases, bounded secret-free evidence and
  principal/query cursor isolation; passive reads cause no Provider/Storage/work/authority effects.
- [ ] **T8:** Current-contract fixes/fixture adaptations and complete affected reruns resolve known
  baseline obligations without deleting assertions, adding retries or relaxing guards/timeouts.
  Exact-candidate T3 evidence and preserved unrelated/private/reference files/refs are verified.

## Required Tests

Follow [test ownership](docs/development-workflow.md#6-test-levels). New test paths below are
**planned additions**, not existing probes/results; equivalent cohesive modules are acceptable
with actual paths/commands in the handoff.

### Developer — affected tests

Add `tests/test_automation_workspace_queries.py` and `tests/test_v2_automation_workspace.py` with
real temporary SQLite/application/authenticated API, controlled clocks and fake/local ports.
Fixtures exceed page bounds with Active/Draft-only, tied/interleaved manual/scheduled admissions,
removed definitions and explicit Job/Task/execution/recovery links. Cover invalid filters/cursors,
unavailable/corrupt evidence, no Active/missing pin, zero/prior-zero denominator, DST/leap/unequal-
month/year boundaries, differing system/Cron/browser zones and no-work/skip/partial/waiting/
cancelled/uncertain states. Separate-connection writers verify coherent reads. Assert filter-before-
limit, deduplication, original/follow-up distinction, correct pre-start/formal/unknown routing and
zero Provider/Storage/admission/configuration side effects.

Run new/changed tests and these directly affected modules (matching broader runs need no repeats):

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_automation_workspace_queries tests.test_v2_automation_workspace
.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_operations_workspace tests.test_automation_definition_occurrence tests.test_v2_automation_operations tests.test_v2_automation_lifecycle tests.test_automation_run_once tests.test_v2_automation_run_once
npm --prefix web run test -- run src/entities/operations/automation.test.ts src/entities/operations/automation-lifecycle.test.ts src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationRunOncePage.test.tsx src/features/operations/run-query.test.ts src/features/operations/OperationsInventory.test.tsx src/routes/router.test.tsx
npm --prefix web run typecheck
npm --prefix web run build
```

Include new/changed Web tests in the actual command; add affected detail/recovery tests if their
shared reads change. Run changed-file Python format/lint/compile and Web ESLint/Prettier using
actual changed paths, not whole-repository gates. After build, run changed/known-failing native
journeys; `automation-workspace.python.spec.ts` is a planned new spec:

```bash
# cwd web
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
```

New native proof starts at actual Automation UI, traverses beyond a page, reads all four cards,
filters manual/scheduled/removed-definition history, follows reason/repair/exact Task Center links
and returns. Verify original result retention after actual independent failed-item recovery with
successful sibling untouched. Faults belong behind reachable real commands in temporary fixtures,
not guessed routes. Retain real overflow refusal alongside bounded success. Mutable-Active
harnesses run sequentially or with isolated ports/configuration/output.

### B — acceptance and regression

Review immutable Task Base..candidate and reassessment-source..candidate, separating integrated45
from43.3 changes. Independently verify beyond-page reachability, Job/Task counted once, original/
linked handling states and sibling safety, repair/Task Center boundary and return, one controlled
calendar boundary and unavailable/cursor isolation. Inspect real wide/narrow reference comparisons;
retain exact source/test/harness/dependency/served-asset identities and raw logs/traces.

B runs the assigned integration/native coverage on the candidate (reuse only matching own/CI
evidence per workflow) plus these acceptance gates:

```bash
.venv/bin/python -m unittest tests.test_operations_task_center tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation
npm --prefix web run test -- run
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run format:check
npm --prefix web run build
npm --prefix web run test:e2e
# cwd web; isolated real-Python harnesses run sequentially
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
```

Full Web unit/default E2E/static gates belong to **B** because shared API/query/router/auth/Task
Center navigation affects other Web surfaces. No full Python/Docker/release sweep is assigned
for unchanged schema/write/resident behavior at T3. Risk escalation/Slice Final T4 still requires
[applicable shared full gates](docs/development-workflow.md#shared-full-regression-commands).
Keep red gates and exact candidate/Base evidence; historical failures are not blanket waivers.
Unavailable required acceptance stays pending, never PASS.

Both roles check scope/private files, `git diff --check` and reference digests:

```bash
shasum -a 256 docs/pics/自动化页.png docs/pics/自动化页-全局设置.png
```

Expected: `d2f759ead56a30dce344ccce97e7c119e144ca728a31b3af8e9a355eefa6ba34` and
`68d91070e859dd363d3e45dd2d21e38783e0cfbef0867ce28c3f42eac7d6c7b9`. Preserve untracked
originals unchanged and the pre-existing `docs/pics/操作与任务.png` deletion. References supply
composition/style, not sample data, removed modes, validation ranges or execution authority.

## Non-goals

- RO-6 settings form/publication/actual resident adoption; queue/concurrency redesign.
- Local record controls/recovery, new retry semantics/results persistence/recovery engine, bulk
  cross-Task mutation, history deletion/retention/rollback or implicit submission.
- Changing lifecycle/publication/grant/admission/Worker execution semantics to make tests pass.
  Required dependencies outside the read unit return to B for explicit plan/risk decision.
- Restoring Scan/standalone Preview/FileIndex or dedicated removed-mode migration/history layers;
  unrelated refactors, new product modes/Providers/Storage paths.
- A Final Review, Slice closure, Roadmap/Progress changes, next Task planning or push.

## Developer Completion Report

### Checkpoint

- Status: **READY FOR B REVIEW**. B's 2026-10-24 FIX-REQUIRED round (R3 ×2 + T8) is implemented in
  the working tree with its affected-test plan and the assigned native matrix executed on it. B
  acceptance (T3 gates, Slice Final T4) remains pending; no self-PASS is claimed.
- Task Base unchanged (`78ec108d4473e8c140174c1356d0e88a1ae42b34`); reassessment source
  `533a666860a571e61c78ac49b3e45c44acaa419e` is not a Base.
- This round starts from B's reviewed candidate `87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12`
  (implementation `29048876f0546efd3ba9c8a5cd5463b7f4b8168f`). Implementation checkpoint:
  `d9157af` (`fix(automation): reconcile recovery per original item and read producer results`);
  this report is its documentation successor, so B reviews
  `87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12..HEAD`. No history rewrite, no push.
- Preserved untouched: the pre-existing `docs/pics/操作与任务.png` deletion, every untracked
  artifact (`.DS_Store`, `.t*.log`, `output/…zip`, `web/test-results*`, untracked `15`) and both
  untracked reference PNGs (digests below). Private config stays ignored/untracked/unstaged.

### Changed behavior — this correction round

1. **R3/P1 — resolution is reconciled per original affected item (T3/T5/T6).**
   `automation_linked_handling` now also computes one bounded coverage read
   (`_automation_handling_coverage_locked`) inside the same transaction. Its *affected* population is
   the record's own durable failed/partial evidence (the Result-first set the failure stage already
   publishes, matched case-insensitively), and an affected item counts as *resolved* only when the
   **same source identity** carries `manual_recovery_preparations.status='confirmed'` →
   `manual_executions` terminally completed → that execution's own
   `manual_execution_items` row with `status='success'`, `effect_certainty='verified_complete'`,
   empty `uncertain_effects` and a `success` Result, joined on
   `json_extract(source_json,'$.storageId'/'$.path')` against the original TaskItem. `_summarize_handling`
   now receives that coverage and refuses to publish `resolved` unless **every** affected item
   carries its own proof: a successful subset of two failures publishes `investigation`
   (`受影响条目 2 · 已确认恢复 1 · 仍未解决 1`) and an execution that left its own failed/uncertain item
   publishes `recovery_failed`. Nothing about the write path, the execution semantics or the stored
   outcomes changed, and no synthetic Task/Job/Result is created.
2. **R3/P1 — durable Result vocabulary and effect certainty are read truthfully (T3/T5/T6).**
   `automation_record_failure_evidence` compares `lower(task_results.status)` so the producer's own
   `FAILED`/`PARTIAL` rows are included (B's reproduced defect: two known-zero-effect failures
   published `effects.partial=2`, `none=0`). TaskItem and Result meanings are kept distinct: a
   Result-backed entry publishes that Result's `effect_certainty`, and only an item with **no**
   durable failure Result falls back to its current TaskItem state — which now reports
   `effectCertainty=unknown` instead of being counted as a `partial` effect. Each entry also
   publishes `statusSource` (`result`/`task_item`) so the two are never conflated. The failure
   reason therefore survives the source item leaving `failed` during recovery: the historical reason
   sample/count no longer drops while handling starts, and both original reasons stay readable
   through analysis, preparation, execution and a durable reopen.
3. **T8 — the real-Python workspace spec is excluded from the default fake-server suite.**
   `web/playwright.config.ts` `testIgnore` gained `**/automation-workspace.python.spec.ts` following
   the established convention for the other real-Python specs. Verified by `--list`: the default
   config now collects **238 tests in 16 files** with **zero** `automation-workspace.python` entries
   (previously all five were collected against the Node fake), while
   `playwright.python.automation.config.ts` still collects it (**21 tests in 3 files** across the
   workspace/lifecycle/run-once specs). No assertion, timeout, gate or fake harness control was
   weakened or removed.
4. **Read/Web surface.** The records row now renders the backend effect partition
   (`已知效果：无效果 n · 已确认 n · 不确定 n · 部分 n`), an explicit unavailable-reason line, and the
   per-item coverage (`受影响条目 / 已确认恢复 / 仍未解决`). `AutomationRecordFailureItemModel` gained
   `statusSource` and the handling model gained `affectedItems`/`resolvedItems`/`unresolvedItems`
   (optional-nullable, so an older document still renders and an unavailable read stays explicit).

### Affected commands and actual results

```text
python3 scripts/check_governance.py                                      PASS
.venv/bin/python -m unittest tests.test_automation_workspace_read_model   tests.test_operations_run_inventory tests.test_operations_run_detail   tests.test_operations_workspace tests.test_automation_definition_occurrence   tests.test_v2_automation_operations tests.test_v2_automation_lifecycle   tests.test_automation_run_once tests.test_v2_automation_run_once   tests.test_automation_api tests.test_task_center_recovery_lineage   tests.test_operations_task_center                                          Ran 307 OK
.venv/bin/python -m unittest tests.test_automation_workspace_read_model   tests.test_operations_run_detail tests.test_operations_task_center   tests.test_task_center_recovery_lineage   tests.test_operations_run_detail_plan_evidence   tests.test_operations_run_detail_log_isolation                            Ran 112 OK
.venv/bin/ruff format --check mediaflow tests scripts                      All formatted
.venv/bin/ruff check mediaflow tests scripts                              All checks passed
.venv/bin/python -m compileall -q mediaflow tests scripts                 OK
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml                        no match (exit 1)
npm --prefix web run test -- run src/entities/operations/automation.test.ts   src/entities/operations/automation-lifecycle.test.ts   src/features/operations/AutomationRouter.test.tsx   src/features/operations/AutomationLifecyclePage.test.tsx   src/features/operations/AutomationRunOncePage.test.tsx   src/features/operations/run-query.test.ts   src/features/operations/OperationsInventory.test.tsx   src/routes/router.test.tsx   src/features/operations/AutomationWorkspaceReadModel.test.tsx            9 files / 114 tests passed
npm --prefix web run typecheck                                            OK
npm --prefix web run lint                                                 OK
npx --prefix web prettier --check <5 changed Web paths>                   All formatted
npm --prefix web run build                                                OK (dist rebuilt)
npx playwright test --config=playwright.config.ts --list                  238 tests / 16 files, 0 workspace-python
npx playwright test --config=playwright.python.automation.config.ts --list 21 tests / 3 files, 5 workspace tests present
git diff --check                                                         clean
shasum -a 256 docs/pics/自动化页.png docs/pics/自动化页-全局设置.png
  d2f759ead56a30dce344ccce97e7c119e144ca728a31b3af8e9a355eefa6ba34
  68d91070e859dd363d3e45dd2d21e38783e0cfbef0867ce28c3f42eac7d6c7b9
```

Native (real Python + SQLite + Local Storage + Scheduler/Worker, rebuilt production asset, isolated
harness, one sequential invocation):

```text
# cwd web, after npm run build
npx playwright test --config=playwright.python.automation.config.ts \
  tests/e2e/automation-workspace.python.spec.ts \
  tests/e2e/automation-lifecycle.python.spec.ts \
  tests/e2e/automation-run-once.python.spec.ts
  21 passed  (28.3s wall clock)
```

Test wall clock for this round was ≈2 min of ≈1 h elapsed (< 30 %). Only focused/changed and
directly affected suites were run; the full Web/default-E2E/static matrix and Slice T4 remain
B-owned and are **not** claimed.

New Python coverage in `tests/test_automation_workspace_read_model.py` (31 → 32 cases):

- `test_handling_requires_every_original_affected_item_to_resolve` — real producer vocabulary
  (`task_results.status='FAILED'`) for two zero-effect failures; asserts the initial
  `effects.none=2` / `partial=0` / `uncertain=0` partition and per-item `effectCertainty='none'`;
  recovers only one item through the actual confirmed-preparation → completed-execution →
  verified-effect chain; asserts `affectedItems=2 / resolvedItems=1 / unresolvedItems=1` with
  state `investigation` (never `resolved`), both original reasons intact, original outcome
  unchanged, and the same read after a real API/runtime reopen. A follow-up with the execution's
  own item failed reverts to `0` resolved.
- `test_handling_progress_is_trueful_across_analysis_plan_and_execution` rewritten at step 4/5 to
  write the real durable per-item chain (`_write_verified_recovery_effect`) instead of only flipping
  a TaskItem status — a completed execution without its own verified effect is no longer accepted as
  resolution.

New native journey in `web/tests/e2e/automation-workspace.python.spec.ts`
(`a recovered subset never resolves the record with a failed sibling`): a real three-item Run once
through the browser with two genuine Executor failures, then a real Task Center recovery of exactly
one. It asserts at the actual records page and via the read-only `/__harness__/automation-record-evidence`
control (which calls the same repository reads the page uses): unchanged original population and
`partial_success`, `effects.none=2` before and after analysis/preparation/execution, the rendered
`已知效果：无效果 2 · 已确认 0 · 不确定 0 · 部分 0`, no `后续处理已完成` at any point, the durable
failed sibling still `failed` with its source present, the successful sibling `success` with its
source gone, `受影响条目 2 · 已确认恢复 1 · 仍未解决 1` after recovery, the identical read after a
real `/__harness__/restart` reopen, and zero local recovery controls on the record. Harness additions
are test infrastructure only and use production paths (`seed-run-once-two-failure-scope`,
`run-run-once-two-failure-worker`, the extended `automation-record-evidence`, and a
`_failure_for_named_execution_items` seam generalizing the existing one-item failure seam — the
supported one-item journey still uses exactly one named source).

### Known failures / remaining risks

- **`statusSource`/coverage counts are Web-contract extensions.** `AutomationRecordFailureItemModel`
  gained `statusSource`; the handling model gained `affectedItems`/`resolvedItems`/`unresolvedItems`.
  The normalizer tolerates their absence (older document) but rejects a malformed value, matching the
  model's existing fail-closed style. No Web unit case was added for the new fields beyond the
  extended `AutomationWorkspaceReadModel.test.tsx` assertions (the read contract and the native
  journey carry the real coverage).
- **Coverage is a separate read from the failure sample.** The handling coverage, the failure-evidence
  sample and the metrics are distinct reads; each publication is internally consistent and says so.
  The coverage predicate intentionally uses the durable Result first, so a record whose *only*
  failure evidence is a currently-failed TaskItem (no Result) still counts as affected with unknown
  effects.
- **A record with no durable affected item can never read `resolved`.** It publishes `investigation`
  with `affectedItems=0`; that is deliberate (an analysis-only lineage must not imply resolution),
  but it means a genuinely fully-successful original run is never labelled as "handled".
- **DST/leap month-boundary rendering remains unit-level**; the counting rule is server-side.
- **`itemsTruncatedByCap` and `stale_page`** are proven in Python, not through the browser.
- **RO-6** (settings publication/actual resident adoption) and the settings portion of AC-1 remain
  **outside** this Task; AC-12's whole-Slice T4 gate is not satisfied by these T3 checks.

### Reusable lesson candidates (Developer)

- Reconciliation must be keyed on the **original affected item's own identity**, not on the newest
  linked attempt's aggregate totals: a completed execution that resolved the subset it admitted
  proves nothing about the sibling the operator never selected.
- A read that compares against a persisted status column must use the **producer's** vocabulary
  (`ExecutionStatus.value` is upper case) or compare case-insensitively; a lower-case-only filter
  silently drops every real manual-execution failure Result.
- "Settled successfully but the record is not done" is a third state, not a failed recovery: publish
  it as inspection with explicit unresolved counts so the operator is sent back to the remaining item
  instead of being told to retry something that already succeeded.

## B Review Result

```text
Reviewed candidate: 87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12 (main; report successor)
Implementation: 29048876f0546efd3ba9c8a5cd5463b7f4b8168f
Task range: 78ec108d4473e8c140174c1356d0e88a1ae42b34..87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12
Reassessment-source range: 533a666860a571e61c78ac49b3e45c44acaa419e..87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12
Correction delta: 383aae3d06e1fb2075d263368d67535e93541fae..87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12
Decision: FIX REQUIRED — R3 still has two independently reproduced P1 outcome defects; T8 default-E2E gate also fails
Base / Goal / Scope / Test Level: unchanged; Task T3, Slice Final T4
Slice Required Outcomes / Surfaces all satisfied: NO
Next: DEVELOPER CORRECTS TASK 43.3; B reviews the next immutable candidate
```

B inspected the full Task-range manifest and separated the accepted45 integration from the26-file
current43.3 delta, then reviewed the current read/query/API/Web/navigation changes and correction.
`2904887..87ec86f` changes only `TASK.md`; executable inputs match the submitted implementation.
This is an early FIX REQUIRED on proven blockers, **not** whole-range acceptance, a rerun/override of
accepted45's A review, or Slice Final. All still-unexecuted acceptance remains B-owned.
The Developer completion report records submitted claims, not B acceptance.

### Required corrections — same Task

1. **R3 / P1 — Resolve the original problem population, not just the newest execution
   (T3/T5/T6).** `_summarize_handling` selects the newest linked execution and treats its own
   positive success count/zero failed count as resolution of the entire original record. A real
   Run once with three recognized files produces one successful sibling and two zero-effect
   failures. Recovering only `Two.2002.mkv` through Task Center analysis → plan summary → explicit
   confirmation → real Worker leaves `Three.2003.mkv` failed with its source still present, yet
   Automation displays `后续处理已完成` and `no further Automation action is needed for this record`.
   Carry the existing durable source-item/continuation/preparation/execution relations into the
   handling read; reconcile relevant outcomes **per original affected item** before aggregating the
   record. A successful subset must not hide an unhandled, failed, active or uncertain sibling,
   nor may an unrelated older/latest attempt prove another item's resolution. Preserve original
   results and conservative investigation when coverage cannot be proved. Reuse existing states
   and lineage; no new workflow, schema, write semantics or local record commands are authorized.
   Add the actual multi-failure/subset journey and prove all affected items must independently
   resolve before the whole record may say resolved, including durable reopen.
2. **R3 / P1 — Read actual durable Result statuses and retain original reason/effect evidence
   (T3/T5/T6).** `automation_record_failure_evidence` filters `task_results.status` with lower-case
   `failed`/`partial`, while the real Manual execution producer persists `ExecutionStatus.value`
   as upper-case `FAILED`/`PARTIAL`. Its TaskItem fallback initially shows a reason but discards the
   known Result certainty: the native fixture's two known-zero-effect failures publish
   `effects.partial=2`, `effects.none=0`, and per-item `effectCertainty=unknown`, despite
   `sideEffects=none`. As soon as recovery analysis moves Two's TaskItem off failed, Two's original
   failure evidence disappears: the original record's reason sample/count drops2→1 before any
   recovery execution. The durable failure Result was not removed. Match the actual existing
   Result vocabulary at the read boundary, keep TaskItem and Result status meanings distinct,
   and derive the bounded historical failure population/effect partitions from those Results.
   Preserve the original stage/reason/known effects while current handling changes; do not rewrite
   stored outcomes, synthesize Results or change the execution producer. Use real producer-backed
   coverage, not only lower-case manually seeded Result fixtures. Assert initial `none=2`, no false
   partial/unknown effect, both original reasons through analysis/preparation/execution and reopen,
   per-Task sample/count isolation, and no successful-sibling effect attributed to a failed item.
3. **T8 — Isolate the real-Python workspace spec from the default fake-server suite.**
   `web/playwright.config.ts` explicitly excludes the other real-Python specs but not the new
   `automation-workspace.python.spec.ts`; the ordinary `npm run test:e2e` therefore collects all
   five of its Python-only journeys against the Node fake. Independently running its first test
   under that default config fails at the existing Create-definition entry after10seconds.
   Add this spec to the established exclusion (or an equivalent minimal existing convention),
   keeping it included under `playwright.python.automation.config.ts`. Verify both configurations'
   test inventories and rerun the affected real native journey. Do not add fake versions of Python
   harness controls, skip the spec everywhere, weaken assertions/timeouts or remove B's default gate.

### Independent reproduction and evidence

The reproduction adapts the **existing** `a record keeps its original result while a handled item
shows separate progress` browser journey. Only the temporary fixture/fault seam changes: add the
already-supported `Three.2003.mkv` candidate beside One/Two, and return the same known-zero-effect
Executor failure for Two and Three. The existing harness driver still claims the browser-admitted
execution and runs the real Manual Worker/OrganizerExecutor. Task Center still handles only Two
through the original UI and supported commands. No product source, route, persisted status or
recovery relation is fabricated or changed for this probe. Passive captures read the real records
responses; the existing per-item harness read confirms the untouched failed sibling and successful
sibling independently. All original journey assertions through confirmed recovery completed; the
added assertion that the record must not claim resolution fails.

| Real checkpoint | Original admission total | Original outcome | Reason items / effects | Handling |
|---|---:|---|---|---|
| Before handling | 1 | partial_success | Two + Three; partial2/none0 incorrectly | unhandled |
| Zero-mutation analysis of Two complete | 1 | partial_success | Three only; Two's historical reason missing | investigation |
| Confirmed recovery of Two complete | 1 | partial_success | Three only; Three still failed/source present | **resolved — incorrect** |

The successful One sibling stays `success`, its source is gone and its Result ID remains present.
The original admission identities/count remain unchanged through recovery: this is meaningful R1
progress, not acceptance of every population/metric/latest case. Analysis alone no longer resolves
this record. Concrete failure category and Task Center ownership render, but the two R3 obligations
above remain unmet. No source/media outside the isolated temporary harness is touched.

Actual B checks on this candidate:

- Governance **PASS**; production Web build **PASS** (≈0.60s).
- `.venv/bin/python -m unittest tests.test_automation_workspace_read_model`: **31 tests OK**
  (≈2.39s). Its manually seeded lower-case failure Result cases do not prove the production format.
- Independent real-Python/UI multi-failure journey: **1 FAILED** (13.85s including assertion wait),
  specifically whole-record resolution while an original failed sibling remains. No retries.
- Default config's existing workspace inventory test: **1 FAILED** (11.26s), Python-only fixture
  running against Node fake. `--list` independently confirms all five Python workspace tests are
  incorrectly collected there. This is not a new product-route probe or an unavailable environment.
- Full Task Base..candidate `git diff --check` clean; both reference PNG digests match the Contract;
  private config remains untracked/unstaged and all pre-existing dirty/untracked files are preserved.
- All other assigned full Web/static/default-E2E/integration/native and visual-reference acceptance
  remains **pending**, not waived or transferred to Developer. Proven-blocker early stop applies.
  No full Python/Docker/packaging run or Slice T4 PASS is claimed.

Durable local evidence (not claimed remotely available):
`.git/validation-evidence/87ec86f0cdbd3c84e901594e5f0dd034f4e0cf12/b-review-20261024/`.
It contains the exact range manifests/diffs, fixture-only driver/spec/config, build/focused logs,
`independent-two-failures.log`, `two-failure-record-responses.json`, screenshot/trace under
`native-output/`, `default-registration.log`/trace, and input/artifact/check timing identities.
The first independent launch encountered an already-occupied port; no existing process was touched;
B switched to an OS-selected free port and then ran the isolated journey. That launch is not a
product failure. Review execution/testing remains below50% of this round's elapsed time.

### Developer affected tests and B retained gates

Correct only these in-Task read/aggregation/test-registration gaps. Run new/changed cases in
`tests.test_automation_workspace_read_model`, the affected Operations/read modules from Required
Tests, and changed Web projection/component tests (`automation.test.ts`,
`AutomationWorkspaceReadModel.test.tsx` as applicable). Use actual produced Result states and
existing source-item lineage. After building production assets, run the three existing Automation
Python specs using `playwright.python.automation.config.ts`, with the mixed test extended to the
multi-failure/subset and exact original-reason/effect assertions above. Check both Playwright test
inventories and changed-file quality checks. Developer does **not** own the full Web/default-E2E or
Slice T4 sweep; B runs the retained assigned acceptance on the corrected candidate.

### All Slice outcomes reassessed

| Outcome / surface | Current B assessment |
|---|---|
| RO-1 inventory/statistics | Implementation progress and31 focused cases; complete query/metric/latest/native acceptance still pending. Settings portion remains outside43.3. |
| RO-2 typed lifecycle/checked Save | Existing implementation reused; this native Create/Save entrance works. Full current lifecycle acceptance is not claimed by this one journey. |
| RO-3 shared analysis/grant/scheduled execution | Shared analysis is reached without retired products; current full grant/scheduled authority acceptance remains pending. |
| RO-4 deliberate Run once | Real three-item discovery/analysis/one-shot admission and execution reached; all other current boundary/reconciliation acceptance remains pending. |
| RO-5 read-only records/recovery | **Incomplete:** false whole-record resolution plus loss/misclassification of original failure evidence above. Task Center ownership and original admission identity are retained. |
| RO-6 settings/real consumer adoption | **Incomplete/outside this Task:** resident loop still retains startup `_poll_seconds`; CLI constructs Worker/Scheduler cadence at startup. A settings link does not complete this outcome. |
| RO-7 shared authority/navigation/failure | Current read surfaces still have R3 defects and the assigned default-E2E gate fails; complete integration acceptance remains pending. |

No next Task, Closure Packet, Roadmap/Progress change or Slice closure follows this FIX REQUIRED.
