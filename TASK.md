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
Decision: FIX REQUIRED — candidate 94aede19095b77af0edffaa74a3da16b7492dd2a; implementation d9157af; latest-result sorting and healthy empty-history state still violate T1/T2; same Task/Base/Goal/Scope
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

- Status: **READY FOR B REVIEW**. B's 2026-10-24 FIX-REQUIRED round is implemented and
  checkpointed with its affected-test plan and the assigned native matrix executed on it. The
  latest round corrects B's two remaining P1 findings (latest-result ordering and
  healthy-empty-history state). B acceptance (T3 gates, Slice Final T4) remains pending; no
  self-PASS is claimed.
- Task Base unchanged (`78ec108d4473e8c140174c1356d0e88a1ae42b34`); reassessment source
  `533a666860a571e61c78ac49b3e45c44acaa419e` is not a Base.
- This round starts from B's reviewed candidate `94aede19095b77af0edffaa74a3da16b7492dd2a`
  (implementation `d9157af`). Implementation checkpoint:
  `eb74f36` (`fix(automation): sort by the latest admitted run and read empty history truthfully`);
  this report is its documentation successor, so B reviews
  `94aede19095b77af0edffaa74a3da16b7492dd2a..HEAD`. No history rewrite, no push.
- Preserved untouched: the pre-existing `docs/pics/操作与任务.png` deletion, every untracked
  artifact (`.DS_Store`, `.t*.log`, `output/…zip`, `web/test-results*`, untracked `15`) and both
  untracked reference PNGs (digests below). Private config stays ignored/untracked/unstaged.

### Changed behavior — latest-result and empty-history correction (last round)

1. **P1/T2 — `最近结果` sorts by the actual latest admitted run.**
   `_automation_inventory_sort_key` no longer reads the scheduled-only
   `occurrenceState.lastOccurrenceAt`; it receives the definition's authoritative latest
   *original admitted* run (manual or scheduled) from `_automation_latest_runs` and orders by that
   `admittedAt`, with the definition identity as the deterministic tie. The ordering therefore uses
   the same value the row publishes, so a manual-only history is ordered by its real admission and a
   never-run definition sorts by the empty key instead of above it. The ordering is applied to the
   complete filtered population **before** the page window, so filter/total/cursor/principal
   semantics are unchanged. A never-run or unreadable row is never sorted by an ID-derived timestamp
   and no non-admitted scheduled diagnostic is merged into the ordering basis.
2. **P1/T1 — a healthy empty history is "no execution", not "unavailable".**
   `_automation_latest_runs` now tracks read success separately from the returned population: the
   durable read answering `{}` is a legitimate global-empty history, a definition absent from a
   successful read is a legitimate per-definition "not yet run", and only a **failed/unavailable**
   read publishes `latestAdmittedRuns[id].unavailable=true` with the refresh next action. The
   previously merged scheduled-occurrence fallback was removed, so a blocked/disabled/scheduled
   diagnostic can never masquerade as a processing result. A healthy empty read publishes no entry
   at all, which the Web already renders as `尚无执行`.
3. **No other surface changed.** No schema, endpoint, write path, admission/execution/Worker
   semantics, permission model or Web component logic was touched; the two Web changes in this round
   are tests only.

### Changed behavior — previous correction round (retained)

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
.venv/bin/python -m unittest tests.test_automation_workspace_read_model   tests.test_operations_run_inventory tests.test_operations_run_detail   tests.test_operations_workspace tests.test_automation_definition_occurrence   tests.test_v2_automation_operations tests.test_v2_automation_lifecycle   tests.test_automation_run_once tests.test_v2_automation_run_once   tests.test_automation_api tests.test_task_center_recovery_lineage   tests.test_operations_task_center                                          Ran 310 OK (49.5s)
.venv/bin/python -m unittest tests.test_automation_workspace_read_model   tests.test_v2_automation_operations tests.test_operations_run_inventory       Ran 94 OK
.venv/bin/ruff format --check mediaflow tests scripts                      All formatted
.venv/bin/ruff check mediaflow tests scripts                              All checks passed
.venv/bin/python -m compileall -q mediaflow tests scripts                 OK
npm --prefix web run test -- run src/entities/operations/automation.test.ts   src/entities/operations/automation-lifecycle.test.ts   src/features/operations/AutomationRouter.test.tsx   src/features/operations/AutomationLifecyclePage.test.tsx   src/features/operations/AutomationRunOncePage.test.tsx   src/features/operations/run-query.test.ts   src/features/operations/OperationsInventory.test.tsx   src/routes/router.test.tsx   src/features/operations/AutomationWorkspaceReadModel.test.tsx            9 files / 115 tests passed (13.2s)
npm --prefix web run typecheck                                            OK
npm --prefix web run lint                                                 OK
npx --prefix web prettier --check   web/tests/e2e/automation-workspace.python.spec.ts   web/src/features/operations/AutomationWorkspaceReadModel.test.tsx        All formatted
npm --prefix web run build                                                OK (dist rebuilt)
npx playwright test --config=playwright.config.ts --list                  238 tests / 16 files, 0 workspace-python
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
  23 passed  (29.9s wall clock)
```

Test wall clock for this round was ≈2.5 min of ≈14 min elapsed (< 30 %): the 310-test Python module
run (49 s), the focused 94-case recheck (13 s), the Web unit run (13.5 s), the single native
invocation (30 s) with two targeted re-runs after fixture adjustments, and the static
format/lint/compile/typecheck/build/prettier checks. Only focused/changed and directly affected
suites were run; the full Web/default-E2E/static matrix and Slice T4 remain B-owned and are **not**
claimed.

New Python coverage in `tests/test_automation_workspace_read_model.py` (32 → 35 cases, all through
the real API/repository/temporary SQLite):

- `test_inventory_latest_sort_uses_the_latest_admitted_run` — two published definitions, one with a
  real manual-only admission (`origin_kind='definition-run-once'`, no scheduled occurrence) and one
  never run, read with `sort=latest&direction=desc`; asserts the manual definition is first, the
  never-run definition still present, `latestAdmittedRuns[manual].admittedAt` equal to the ordering
  evidence and no fabricated entry for the never-run definition. Reverting
  `_automation_inventory_sort_key` to the old `lastOccurrenceAt` basis fails this case with
  `'z-review-never' != 'a-review-manual'` — B's exact reproduced defect.
- `test_inventory_latest_sort_is_total_and_pageable` — three definitions, two sharing one admission
  instant and one older, plus the never-run seeded definition; walks `limit=1` forward pages through
  the real cursors asserting no duplicate/repeated boundary row, the deterministic identity tie, and
  the never-run definition last.
- `test_inventory_latest_run_state_distinguishes_empty_from_unreadable` — healthy global-empty read
  (`{}`, no `unavailable` entry, available metrics), then a sibling with history beside a never-run
  definition (only the run definition published), then a genuine fault seam on the repository method
  publishing `unavailable=true` with the refresh action for **every** definition while the cards stay
  available and correct. Reverting to the old `unavailable = not admitted` rule fails this case.

New/changed Web coverage:

- `AutomationWorkspaceReadModel.test.tsx` gained `labels a healthy empty history as no execution, not
  unavailable` (empty `latestAdmittedRuns` → `尚无执行`, no `最近结果不可用`, cards still published).
- `web/tests/e2e/automation-workspace.python.spec.ts` gained two real-UI journeys:
  `the latest-result sort uses the real admitted history` (publish `a-review-manual`, run it once
  through the real discovery → frozen plan → explicit confirmation → Worker path, then publish the
  never-run `z-review-never`, select `排序 → 最近结果`, assert the submitted
  `sort=latest` GET and that the genuinely-run row precedes the never-run row while the never-run row
  still reads `尚无执行`) and `a healthy empty history reads as no execution, not unavailable`
  (publish a definition nobody has run, assert `尚无执行`, no `最近结果不可用`, available cards). The
  shared `publishDefinition` helper gained an optional `definitionId` so these journeys use their own
  definition identities instead of inheriting another test's admitted history.

Retained from the previous round and re-executed here: the R3 per-original-item reconciliation, the
producer Result vocabulary, the durable reason/effect retention, the `_failure_for_named_execution_items`
seam, independent sibling non-replay, real reopen evidence, and the T8 default-config exclusion.

### Known failures / remaining risks

- **The latest-result ordering is a read-model projection, not a new query contract.**
  `_automation_inventory_sort_key` now consumes the same `_automation_latest_runs` projection the
  response publishes, so ordering, the echoed `latestAdmittedRuns` and the rendered row cannot
  disagree. That projection is still the single durable
  `automation_latest_admitted_runs` aggregation (one SQL statement over the admitted-run population,
  first row per definition identity) already reviewed in the previous round; no new endpoint, window
  parameter or result store was added, and this Task's T3 scope does not authorize changing that
  query's shape.
- **An unreadable latest-run read degrades the `最近结果` ordering.** When the durable read fails,
  every row sorts by the empty key plus its identity tie while each row is explicitly labelled
  `最近结果不可用`. That is deliberate (nothing is invented) but the ordering is then effectively
  identity order for that one request.
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
- **The native latest-sort journey asserts order, not a screenshot diff.** The wide/narrow workspace
  screenshots were inspected this round against the preserved reference and are unchanged by this
  correction (no component code changed); pixel-level visual acceptance remains B's.
- **RO-6** (settings publication/actual resident adoption) and the settings portion of AC-1 remain
  **outside** this Task; AC-12's whole-Slice T4 gate is not satisfied by these T3 checks.

### Reusable lesson candidates (Developer)

- A sort key must be the **same published evidence** the row shows. Ordering by a sibling projection
  (`occurrenceState.lastOccurrenceAt`) while publishing a merged manual/scheduled value produced a
  table whose first row was contradicted by its own `最近结果` cell, and no amount of correct row
  rendering could hide it.
- "No rows" is an answer; "I could not read" is a different answer. Collapse them
  (`unavailable = not admitted`) and every healthy empty history becomes an error state, while a real
  fault becomes indistinguishable from an empty library. Track read success and read population
  separately at the boundary where the read happens.
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
Reviewed candidate: 94aede19095b77af0edffaa74a3da16b7492dd2a (main; report successor)
Implementation: d9157af (2026-10-24 correction)
Task range: 78ec108d4473e8c140174c1356d0e88a1ae42b34..94aede19095b77af0edffaa74a3da16b7492dd2a
Reassessment-source range: 533a666860a571e61c78ac49b3e45c44acaa419e..94aede19095b77af0edffaa74a3da16b7492dd2a
Correction range: 744d9dc..94aede19095b77af0edffaa74a3da16b7492dd2a
Decision: FIX REQUIRED — T1/T2 required latest-result and empty-history read semantics remain incorrect
Base / Goal / Scope / Test Level: unchanged; Task T3, Slice Final T4
Slice Required Outcomes / Surfaces all satisfied: NO
Next: DEVELOPER CORRECTS THE SAME TASK; B retains corrected-candidate acceptance
```

B reviewed the full immutable Task-range manifest, separating the already accepted45 integration
from the current27-file43.3 read/query/API/Web/navigation delta, and inspected the correction.
`d9157af..94aede1` changes only `TASK.md`. This is independent whole-Task review with proven-blocker
early stop, **not** whole-range acceptance, A Final Review, closed45 reapproval or Slice Final.
The Developer report above remains submitted evidence, not self-acceptance.

### Verified corrections from the prior review

- **R3 per-original-item handling:** the real three-item Run once produces one success and two
  known-zero-effect failures. Recovering exactly one failure through Task Center analysis → exact
  summary → explicit confirmation → real Worker leaves handling `investigation`, with
  `affectedItems=2 / resolvedItems=1 / unresolvedItems=1`; the other source remains failed/present.
  The successful sibling remains complete. The same evidence survives a real runtime reopen.
  The one-failure/all-affected recovery journey also passes; analysis alone never proves resolution.
- **R3 original reason/effects:** the native producer's uppercase failure Results are retained;
  both original reasons and `effects.none=2` survive analysis/preparation/execution/reopen, with
  no false partial/unknown partition and no original result/count rewrite. The32 read-model
  cases and assigned affected integration modules pass on this candidate.
- **T8 registration:** default `--list` independently reports238 tests/16files and zero
  workspace-python entries; the real-Python Automation invocation still executes all six
  workspace cases (21 cases total across three specs). This fixes collection isolation, not a
  claim that the still-unrun full default suite is green.

### Required corrections — same Task

1. **P1 / T2 / RO-1 — Sort the actual latest admitted result, not scheduled-only state.**
   From the existing UI, B creates `a-review-manual`, runs its saved scope through discovery,
   frozen manifest, exact summary and explicit confirmation, then creates `z-review-never`
   without running it. Selecting `排序 → 最近结果` submits the real inventory GET with
   `sort=latest` / `direction=desc`. The same200 response publishes A's genuine manual
   `admittedAt`/trigger yet orders `[z-review-never, a-review-manual]`. The actual table shows
   the never-run definition first. `_automation_inventory_sort_key` still reads
   `occurrenceState.lastOccurrenceAt`; `_automation_latest_runs` supplies the manual/scheduled
   admitted value only to a separate map. Use the authoritative latest-original-admission
   value as the shared row/sort/page basis before windowing, with a deterministic identity tie.
   Keep never-run/unavailable states explicit; do not sort a manual-only history by ID or let
   a non-admitted scheduled diagnostic masquerade as a processing result. Preserve all query/
   cursor/principal safety. Add mixed manual/scheduled/never-run ordering, tied-time and
   beyond-page forward/back coverage, plus this real UI latest-sort journey. Do not remove
   the offered sort or weaken the assertion.
2. **P1 / T1 / RO-1/RO-7 — Distinguish a successful empty history from an unreadable history.**
   The existing real temporary configuration/SQLite fixture has a healthy published enabled
   definition and no admitted runs. The repository's latest-admission read succeeds with `{}`;
   the authenticated public inventory GET returns200 and available metrics, but publishes
   `latestAdmittedRuns.auto-task.unavailable=true` and says the durable history could not be
   read. The Web consequently labels a legitimate empty history `最近结果不可用` instead of
   `尚无执行`. `_automation_latest_runs` conflates `{}` with failure at
   `unavailable = not callable(reader) or not admitted`. Track read success separately from
   returned population. A healthy empty or per-definition absent history must mean no execution;
   a failed/unavailable read must remain explicitly unavailable, never borrowed scheduled success
   or fabricated no-execution. Cover healthy global-empty, no run for one definition beside a
   sibling with history, and a genuine fault-seam unreadable read through the existing public
   inventory/Web contract. No schema, write semantics, new endpoint or workflow is needed.

These are required current Task surfaces, not optional process improvements. Correct only the
read/projection/ordering and their focused tests; retain the previous recovery fixes and accepted45
boundaries. Both corrections stay inside the existing High/T3 unit; no new Task/fix ladder or
A-owned Contract change is requested.

### Independent commands and actual results

| Check on the submitted candidate | B result |
|---|---|
| `python3 scripts/check_governance.py` | PASS |
| `.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_operations_workspace tests.test_automation_definition_occurrence tests.test_v2_automation_operations tests.test_v2_automation_lifecycle tests.test_automation_run_once tests.test_v2_automation_run_once tests.test_automation_api tests.test_task_center_recovery_lineage tests.test_operations_task_center tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation` |324 tests OK;32 workspace cases included;50.75s wall clock |
| `npm --prefix web run test -- run` |80 files /1172 passed;59.07s |
| `npm --prefix web run typecheck`, `lint`, `format:check`, `build` |All PASS; actual logs retained |
| `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts --output=<evidence>/automation-native-output` (cwd `web/`) |21 passed;29.06s wall clock; no retries |
| Default `npm run test:e2e -- --list` (cwd `web/`) |238 tests/16files;0 workspace-python entries |
| Independent existing-UI latest-sort journey (ignored config/spec) |1 FAILED at actual result-order assertion;3.12s; all admission and latest-evidence assertions reached |
| Existing real empty-history fixture → authenticated inventory GET |200; healthy `{}` incorrectly labelled unavailable; raw response saved |

The native proof uses unchanged production code, original harness and supported UI/commands. Only
legal fixture definition IDs/names and the sorting assertion differ from the existing journey;
there is no guessed endpoint, direct status edit or impossible product state. The empty-history
probe uses the existing `_runtime`/`_request` test fixture and public read route, without injected
exceptions. Desktop/narrow workspace and Run-once screenshots were visually inspected against
the original reference: composition is present, but that does not certify the unmet read semantics.
SQLite ResourceWarnings, jsdom scrollTo and build chunk-size warnings are retained, not suppressed.

Local-only evidence (not claimed remotely available):
`.git/validation-evidence/94aede19095b77af0edffaa74a3da16b7492dd2a/b-review-20261024/`.
`INDEX.md` gives actual commands, reproduction, source/config/dependency/served-artifact identity
and attribution. Logs, full diff/manifest, `latest-sort-response.json`, empty-history response,
independent config/spec, screenshots/DOM/trace and `timing.jsonl` are retained there.

### Developer affected checks / B retained acceptance

Run new/changed latest/read-state cases in `tests.test_automation_workspace_read_model`, plus
`tests.test_operations_run_inventory` and `tests.test_v2_automation_operations` where affected.
Run the changed entity/component tests (`automation.test.ts`,
`AutomationWorkspaceReadModel.test.tsx`, Router/navigation tests if touched), changed-file quality
checks, typecheck and build. After build, run the existing three-spec real Automation invocation
with the new two-definition/latest-sort and healthy-empty-history assertions. Preserve the native
multi-failure/subset, actual Result vocabulary, original reason/effect, non-replay and reopen proofs.
Developer does not own full Web/default-E2E/Operations/Unicode/Slice T4 gates.

B stops the remaining expensive gates after the proven required-outcome blockers. Full default
E2E, real `operations-inventory.python.spec.ts`, Unicode-principal native acceptance, and any
still-missing whole-Task query/visual acceptance remain **pending**, not waived or transferred.
No full Python/Docker/packaging or Slice T4 PASS is claimed. Current passing checks may be reused
only if their executable inputs match under the workflow; changed inputs need fresh acceptance.

### All Slice outcomes reassessed

| Outcome / surface | Current B assessment |
|---|---|
| RO-1 inventory/statistics |Full-population cards and read queries have meaningful integration/native proof; required latest-result sorting and healthy-empty-history state are still blocked. Settings portion remains outside43.3. |
| RO-2 lifecycle/checked Save |Current eleven-case real lifecycle matrix passes, including durable Save, enable/copy/remove, unknown-response reconciliation and retained/corrupt history. This is not historical43.1 PASS reuse or A whole-outcome acceptance. |
| RO-3 shared analysis/grant/scheduled execution |Current affected Python tests and native scheduled-record/analysis paths pass; no retired Preview product restored. Complete Contract-level unattended/safety/T4 acceptance is not claimed. |
| RO-4 deliberate Run once |Current four-case Run-once native suite passes, including exact frozen plan/restart and independent recovery; no schedule/authority rewrite. Further Contract safety proof remains in Slice Final. |
| RO-5 records/recovery |Original-result retention, per-item handling, durable reasons/effects and Task Center ownership/return now pass current native cases; latest-result truth is not fully accepted while the RO-1 read defects remain. |
| RO-6 actual settings consumption |Still incomplete and outside43.3: four-field settings/real resident cadence adoption requires its later coherent unit; a navigation link/API rebinding is not adoption. |
| RO-7 shared safety/failure/return |324 affected integration cases, full Web1172, static checks and Automation native pass; empty-read semantics still fail and default/Operations/Unicode acceptance remains pending. |

**Decision remains FIX REQUIRED on43.3.** Do not plan43.4 yet, change Slice/Roadmap/Progress,
prepare a Closure Packet or claim Slice READY/CLOSED. Preserve all pre-existing dirty/untracked/
private files, original reference PNG hashes and preservation refs. Only B-owned Task review/status
is checkpointed; no product implementation, push or history rewrite is performed in this review.

Testing/checking time recorded at this review write: **161.56s / 704.85s elapsed (22.9%)**, strictly below50%; final timing and scope checks are retained in the evidence index.
