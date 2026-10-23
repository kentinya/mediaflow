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
Decision: FIX REQUIRED — candidate 2b75fe98362a58aaf4c7b4b01e19d1a1fd76dede; implementation f0c42784ad3fe6b748cd9457bc440a83e37346e1; same Task/Base/Goal/Scope
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

- Status: **READY FOR B REVIEW**. FIX-REQUIRED round R1–R4 delivered; affected-test plan executed on
  the working tree below. B acceptance (T3 gates, Slice Final T4) remains pending.
- Task Base unchanged (`78ec108d4473e8c140174c1356d0e88a1ae42b34`); reassessment source
  `533a666860a571e61c78ac49b3e45c44acaa419e` is not a Base.
- Implementation checkpoint: `f0c42784ad3fe6b748cd9457bc440a83e37346e1` (parent
  `7e1aa92889932b50044d14d09115577580bb1529`); this report is a documentation successor of that
  candidate, so B reviews `7e1aa92889932b50044d14d09115577580bb1529..HEAD`.

### Changed behavior — R1..R4

1. **R1 — one mandatory original-Automation-admission population.**
   `_run_query_clauses`/`operations_runs_window`/`operations_runs_page`/`list_operations_runs` take
   an `automation_admissions` predicate applied **before** the page window, filtered total, status
   partitions and metric aggregation:
   `(run_kind='job' AND (schedule_id IS NOT NULL OR definition_id IS NOT NULL)) OR
   (run_kind='task' AND origin_definition_id IS NOT NULL)`. `_automation_records_page` always submits
   it, and `automation_run_metrics` uses the identical SQL predicate. Ordinary Files/CLI Jobs,
   standalone manual organize Tasks, preparation-only discoveries, rejected/blocked attempts and
   recovery follow-up Jobs/Tasks therefore never appear in Automation records, totals or cards.
   Result semantics are now durable item evidence: `organization_success_items` /
   `uncertain_success_items` are derived per run from `task_items` + the latest `task_results`
   effect_certainty. A terminal `completed` run counts as organization success only with ≥1 proven
   success item and no uncertain success item; `noWorkCount` labels a successful no-work completion,
   and the success denominator keeps failed/partial/cancelled/terminal-uncertain. The metric test
   that previously counted unrelated standalone Tasks was corrected, and mixed-population plus
   no-work/uncertain cases were added.
2. **R2 — full-population inventory aggregates and merged latest execution.**
   `GET /api/v1/operations/automation/task-definitions` now returns `inventoryCounts`
   (`published`/`enabled`/`draftOnly`/`total`, basis `exact_current_active_and_open_drafts`) computed
   over the complete authorized definition population **before** filters and paging, and embeds it in
   `metrics.inventory`. Draft-only rows stay reachable and labelled but are never counted as
   published/enabled. `latestAdmittedRuns` merges the scheduled-occurrence projection with new
   repository evidence (`automation_latest_admitted_runs`, one newest original admitted run per
   definition written by an admission), so a manual-only definition reports its real latest result
   and each latest row carries `organized`/`noWork`/success/uncertain item counts and the real
   execution window. Web consumes `inventoryCounts` and `latestAdmittedRuns` directly; the previous
   page-derived `enabledCount`/`pendingCount` and the filter-suppression of totals are gone.
3. **R3 — result/reason and separately linked handling.**
   `OperationsRunOverview` gained `execution_started_at`/`execution_finished_at` (Job
   `started_at`/`completed_at`, Task `started_at`/`completed_at`; `created_at`/`updated_at` are never
   reused) plus `organization_success_items`/`uncertain_success_items` and the `organized_successfully`
   /`no_work_completion` properties. `_automation_record_document` now publishes `result` (status,
   organized, noWork, success/uncertain item counts, statement), `failureStage` (bounded stage,
   category, next action, statement — pre-start repair vs formal-Task stage), `nextAction` (closed
   kind plus statement and exact run/definition identity) and `handling` as a **separate** state
   (`unhandled`/`handling`/`recovered`/`recovery_failed`/`investigation`/`unavailable`) from a new
   repository read `automation_linked_handling` that joins only persisted
   `recovery_continuations`/`scope_continuations`/`metadata_correction_continuations`/
   `manual_recovery_preparations`+`manual_executions` rows for the page's own Task IDs. The original
   failed/partial outcome is never rewritten. `AutomationRecordRow` renders the real window, the
   original result statement, the stage/reason, the separate handling badge/next action and the
   exact Task Center/definition links — still with no local recovery control. A record whose read
   genuinely failed stays `unavailable`; a pre-Task admission is honestly `unhandled`.
4. **R4 — direction + persistent navigation + time controls.**
   `AutomationRecordsQueryOptions.direction` is now carried through `automationRecordsUrl`, the
   TanStack query key and `fetchAutomationRecords`, matching the backend's
   `automation records query accepts ... direction` contract; the first → next → previous round trip
   now works through the real Web controls. `AutomationListPage` moved its tab, definition/record
   filters, sort and server page cursor into the route search (free-text inputs are local drafts
   submitted on Enter/blur), so a reload, a reconnect and a return from a definition or Task Center
   page restore the same population. `执行记录` gained bounded UTC start/end `datetime-local`
   controls wired to the backend `from`/`to` filters. New `shared/navigation/automation-return.ts`
   and `automation-list-return.ts` re-validate the preserved context key by key;
   `destination-model.ts` allowlists the Automation list state (`tab`, filters, cursor, `dir`,
   `returnTab`) for Authentication continuations and Automation detail routes. Definition/lifecycle
   back links submit that preserved state, and the Task Center offers
   `返回自动化执行记录` for the record round trip.

### Affected commands and actual results

```text
python3 scripts/check_governance.py                                    PASS
.venv/bin/python -m unittest tests.test_automation_workspace_read_model
                                                                      Ran 24 OK (8 new R1–R4 cases)
.venv/bin/python -m unittest tests.test_automation_workspace_read_model \
  tests.test_operations_run_inventory tests.test_operations_run_detail \
  tests.test_operations_workspace tests.test_automation_definition_occurrence \
  tests.test_v2_automation_operations tests.test_v2_automation_lifecycle \
  tests.test_automation_run_once tests.test_v2_automation_run_once \
  tests.test_operations_task_center tests.test_operations_run_detail_plan_evidence \
  tests.test_operations_run_detail_log_isolation tests.test_automation_api \
  tests.test_system_settings_management tests.test_automation_admission \
  tests.test_automation_authorized_execution_matrix \
  tests.test_automation_definition_execution                        Ran 374 OK
.venv/bin/python -m unittest tests.test_automation_job_fencing \
  tests.test_automation_task_definition tests.test_automation_definition_publication \
  tests.test_automation_unattended_grant                             Ran 74  OK
.venv/bin/ruff format --check mediaflow tests scripts                350 files already formatted
.venv/bin/ruff check mediaflow tests scripts                         All checks passed
.venv/bin/python -m compileall -q mediaflow tests scripts            OK
.venv/bin/mediaflow --config config/strategy.example.json config validate
                                                                     PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
                                                                     PASS
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml                   no match (exit 1)
npm --prefix web run typecheck                                       OK
npm --prefix web run lint                                            OK
npm --prefix web run format:check                                    All matched files formatted
npm --prefix web run build                                           OK (dist rebuilt)
npm --prefix web run test -- run                                     80 files / 1172 tests passed
git diff --check                                                     clean
shasum -a 256 docs/pics/自动化页.png docs/pics/自动化页-全局设置.png
  d2f759ead56a30dce344ccce97e7c119e144ca728a31b3af8e9a355eefa6ba34
  68d91070e859dd363d3e45dd2d21e38783e0cfbef0867ce28c3f42eac7d6c7b9
```

New Web coverage: `web/src/features/operations/AutomationWorkspaceReadModel.test.tsx` (7 cases:
fixture normalizers, full-population cards under filtering, no-work labelling, unavailable
latest-result labelling, original result + real window + failure stage + separate handling + no
local control, backward paging direction, URL-persisted tab/filter across a reload). Existing
`automation.test.ts`/`AutomationRouter.test.tsx` fixtures were updated to the new required
projection fields.

Native (real Python + SQLite + Storage + Scheduler/Worker, built asset, isolated harness 4185):

```text
# cwd web, after npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts \
  tests/e2e/automation-workspace.python.spec.ts \
  tests/e2e/automation-lifecycle.python.spec.ts \
  tests/e2e/automation-run-once.python.spec.ts
  20 passed  (5 workspace specs — 2 new; all 15 pre-existing lifecycle/Run-once specs)
```

The new workspace specs prove, through the real UI: full-population cards unchanged while filtering
and paging; a manual-only latest run surfaced from merged admitted-run evidence; the read-only
records surface with no command and no invented Task Center link for a pre-Task admission; a
scheduled record population of >20 real Scheduler emissions traversed first → next → previous through
the real controls with `direction=previous` observed on the wire and the definition filter retained
across reload; and the mixed-item Run-once recovery journey re-reading Automation before/after
recovery to show the original partial result, its failure stage and a separately linked `正在处理`
handling state, no extra original admission, then an exact Task Center round trip back to the same
filtered records list. Test wall clock stayed well below 30% of this round's working time.

New harness controls (test infrastructure only, real production paths):
`POST /__harness__/seed-automation-record-page` emits N real Scheduler occurrences dated in the past,
and `POST /__harness__/run-automation-definition-worker?definitionId=…` scopes the Worker claim to an
explicitly named definition.

### Known failures / remaining risks

- **DST/leap month-boundary rendering is unit-level only.** `test_metric_windows_clamp_the_previous_period_at_month_end`
  asserts the clamped previous window and a leap-February start; a full cross-timezone *browser*
  render of a month boundary is not exercised. The counting rule is server-side.
- **Corrupt/oversized managed sections** remain bounded by `_AUTOMATION_INVENTORY_CAP` and reported
  via `itemsTruncatedByCap`; only the existing corrupt-published-evidence native test covers the
  corrupt path end-to-end.
- **`itemsTruncatedByCap` and `stale_page`** are proven in Python, not reproduced through the browser.
- **Separate-connection deep pagination:** the read model's page/total/status counts and the metric
  aggregates each come from their own read call; a concurrent writer between two calls can make the
  two *separately published* documents differ. Each publication is internally consistent and
  explicitly says so; they are not claimed to be one snapshot across surfaces.
- `automationMetricsQueryOptions`/`fetchAutomationMetrics` remain available as an independent
  `/api/v1/operations/automation/metrics` read; the list page embeds the same document, so nothing
  renders two possibly-different card sets.
- **RO-6** (settings form/publication/actual resident adoption) and the settings portion of AC-1
  remain **outside** this Task and incomplete; the settings tab is a link only, and no adoption is
  claimed. AC-12's whole-Slice T4 gate is not satisfied by these T3 checks.
- Pre-existing untracked workspace artifacts (`.DS_Store` files, `.t*.log`, `output/…zip`,
  `web/test-results*`, untracked `15`) and the pre-existing `docs/pics/操作与任务.png` deletion are
  preserved untouched. Both reference PNGs stay untracked with the verified digests. No private
  configuration was read or changed.

### Reusable lesson candidates (Developer)

- A shared read model that many surfaces consume needs the population predicate as a **first-class
  query parameter**, not a caller convention: one surface silently reporting every run is a
  data-truth bug, not a display bug.
- "Latest outcome" must merge every durable admission family; a scheduled-only projection makes a
  manual-only history read as "never ran".
- A cumulative record surface must label the follow-up handling state separately and keep
  `created_at`/`updated_at` distinct from a real execution window, or a pending row displays an
  end time and an old failure reads as resolved.

## B Review Result

```text
Reviewed candidate: 2b75fe98362a58aaf4c7b4b01e19d1a1fd76dede (main; report successor)
Implementation: f0c42784ad3fe6b748cd9457bc440a83e37346e1
Task range: 78ec108d4473e8c140174c1356d0e88a1ae42b34..2b75fe98362a58aaf4c7b4b01e19d1a1fd76dede
Reassessment-source range: 533a666860a571e61c78ac49b3e45c44acaa419e..2b75fe98362a58aaf4c7b4b01e19d1a1fd76dede
Correction delta: 7e1aa92889932b50044d14d09115577580bb1529..2b75fe98362a58aaf4c7b4b01e19d1a1fd76dede
Decision: FIX REQUIRED — remaining in-Task P1 outcome gaps R1/R3
Base / Goal / Scope / Test Level: unchanged; Task T3, Slice Final T4
Slice Required Outcomes / Surfaces all satisfied: NO (RO-1/5 incomplete; RO-6 outside this unit)
Next: DEVELOPER CORRECTS TASK 43.3; B reviews the next immutable candidate
```

The original Base range includes accepted45; its implementation/closure references and retired
entrances remain intact. B inspected the current correction separately and stopped before expensive
acceptance after independently confirmed blockers. This is not whole-range acceptance or Slice Final.
`f0c4278..2b75fe9` changes only `TASK.md`; the tested executable inputs are the submitted candidate's.
The Developer report above records submitted claims, not B acceptance.

### Observed progress and remaining gates

- Code now supplies backend full-population published/enabled/Draft counts, merges admitted manual
  history, uses real execution timestamps and carries record paging direction, URL state and time
  controls. R2/R4 have implementation progress; their assigned native/query/read-consistency and
  full Web acceptance is still pending. No prior requirement or gate is waived.
- The real mixed-item journey preserves the original `partial_success` result and the successful
  sibling's independent result/source state through failed-item analysis, plan confirmation and
  actual recovery execution. Records retain Task Center ownership and no local recovery control.
- Remaining R1/R3 failures below prevent the truthful records/statistics outcome. Developer fixes
  these in the same Task and runs failing/new/changed/directly affected checks. B retains the full
  assigned integration/native/Web/static matrix and all other acceptance obligations. No next Task,
  Closure Packet, settings completion or Slice closure follows this verdict.

### Required corrections — same Task

1. **R1 / P1 — Exclude linked recovery execution even when it inherits definition origin
   (T3/T4/T5).** The new mandatory predicate accepts every standalone Task with
   `origin_definition_id`. Existing supported recovery execution inherits that origin through
   `ManualOrganizeExecutionService._with_definition_origin`; therefore it still becomes another
   original Automation admission. In the real journey, unfiltered records total stays2 through
   analysis/preparation, then becomes3 immediately after recovery execution confirmation.
   The extra row is a new `manual_organize` Task for `harness-run-once`; the other two rows are the
   original manual run and a genuine scheduled admission, not a recovery analysis Job.
   Use persisted recovery/preparation/execution lineage to distinguish original from follow-up
   before LIMIT, total, status-count, metric and per-definition latest selection. Apply one matching
   population rule across those consumers. Preserve origin/history and existing write semantics;
   do not remove origin to hide this read bug. Assert numeric totals, identities, metrics and latest
   before/after actual recovery execution, including after reopen, with ordinary/non-admitted work
   excluded and genuine manual/scheduled originals retained.
2. **R3 / P1 — Derive handling from verified relevant resolution, not completed analysis
   (T3/T5/T6).** `_summarize_handling` treats any completed non-preparation continuation, or any
   completed linked execution status, as resolution without verifying relevant item/effect evidence.
   Existing recovery continuation `completed` means successful zero-mutation DryRun analysis.
   At that point the actual Automation row says `后续处理已完成` and
   `no further Automation action is needed for this record`, before a new plan is confirmed or
   executed. Preparing the legitimate plan then changes it to `investigation`; an admitted pending
   execution also remains `investigation`. Project analysis-ready/prepared/admitted/running progress
   truthfully within the separate handling model. Require verified linked execution/item/checkpoint
   outcomes for resolution of the relevant original problems; an older completed attempt cannot
   hide remaining failed/active/uncertain items. Keep original results unchanged, ambiguous evidence
   as investigation, and failed reads as unavailable rather than unhandled. Read failure currently
   falls through `_automation_handling_evidence`'s empty mapping, so preserve the distinction there.
3. **R3 / P1 — Show the original concrete failure reason and known effects (T3/T5/T6).**
   `_automation_record_failure_stage` returns `linked_task_stage`, null category/nextAction and a
   generic Task Center referral for the real formal-Task failure. The page still does not tell the
   operator why it failed. The exact existing Task Center item read already supplies
   `storage_failure`, a bounded message, durable failed TaskItem/Result, `sideEffects: none`, safe
   repeatability and the instruction to inspect source/destination state before explicit retry.
   Reuse that bounded authoritative evidence for original reason/stage, per-item known/uncertain
   effects and concrete guidance; render it in records/reason expansion with the exact run/problem
   link. Keep the successful sibling's effect distinct from the failed item's zero effect.
   Do not expose raw exceptions or add local commands. The existing reached-bound obligation also
   remains: `_automation_record_reached_bound` unconditionally returns false; derive supported
   evidence or explicitly label unavailable, without claiming exhaustion. This review does not
   claim that the mixed fixture itself reached its bound.

### Independent native evidence

The reproduction adapts the **existing** `Run once preserves a successful sibling while one failed
item is recovered` journey, using the existing Automation/Task Center UI and supported records/item
reads. It adds passive captures at real workflow checkpoints and one assertion excluding resolution
after analysis alone. All original steps through actual recovery and successful-sibling assertions
completed; the added assertion fails as expected. No guessed route, user media or runtime database
was used. The isolated real Python/SQLite/Local Storage/Scheduler/Worker harness ran on port4190
against rebuilt production assets and was stopped after the test.

| Actual checkpoint | Unfiltered original-run total | Original outcome | Reported handling |
|---|---:|---|---|
| Failed-item recovery admitted | 2 | partial_success | handling |
| Zero-mutation analysis completed | 2 | partial_success | **resolved — incorrect** |
| New plan prepared | 2 | partial_success | investigation |
| Recovery execution admitted | **3 — incorrect** | partial_success | investigation |
| Recovery execution completed | 3 | partial_success | resolved |

Required affected coverage is the existing read-model Python module, changed Web projection tests
and lifecycle/Run-once/workspace native journeys from the plan. Extend the real mixed-item test to
assert each intermediate handling state, exact numeric totals and concrete failure reasons, then
actual verified recovery with the sibling untouched. The shipped workspace spec currently compares
occurrences of the text `条执行记录`, not its numeric total, and accepts any of three handling labels
before executing recovery; those assertions do not prove the claimed outcome. Keep the original
safety assertions and make the new checks exact, without retries or weakened guards.

### B checks and evidence

- Governance **PASS**; rebuilt production Web **PASS**; Task Base..candidate `git diff --check`
  clean. The independent native reproduction is **1 FAILED** at
  `analysis completion is not recovery resolution`; its full raw trace includes the count and
  reason defects above. No other assigned B gate is claimed as executed on this candidate.
- Durable local evidence (not claimed remotely available):
  `.git/validation-evidence/2b75fe98362a58aaf4c7b4b01e19d1a1fd76dede/b-review-20261024/`.
  Read `recovery-checkpoints.json`, `native-record-responses.json`,
  `native-run-item-responses.json`, `original-failure-evidence.json`,
  `independent-recovery.log` and `native-output/.../trace.zip` plus
  `analysis-only-automation.png`; input/artifact digests and final check/timing records accompany
  them. Both reference PNG digests still match. Pre-existing dirty/untracked/private files remain
  untouched; only this B-owned Task review is checkpointed.
- Build/native execution took approximately6.3seconds, with governance/check overhead recorded
  separately; total measured verification remains below50% of this review's elapsed time.
  Required expensive gates remain pending under workflow's proven-blocker early-stop rule, with
  no transfer to Developer. B performs them on the corrected fixed candidate.
