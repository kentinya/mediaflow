# Task 42.2 — Native run detail, progress and operation evidence

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.2
Parent Slice: 42
Status: FIX REQUIRED
Task Base: cf7099a478a203f3f29ac57ef5b8acc295aadaa9
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authenticated operator selects a run in `操作与任务`, understands its actual progress and each
item's outcome in `任务详情`, inspects its durable plan/results/steps in `操作记录`, and exports the
eligible task-scoped JSON result package without leaving the native V2 journey. Complete RO-3 and
its RO-1/RO-7 detail, context and privacy integration; this Task does not complete RO-4–RO-6.

## Why This Task Exists

At Task Base, the inventory has one linked Job/Task population, historical scope and an exact
selected-run overview. `OperationsLanding.tsx::RunDetailFacts` still shows aggregate counters and
links to separate Task/Job pages rather than the reference's complete detail/records journey.
`TaskDetailPage.tsx` has separately paged items/results and backend lifecycle facts, but lacks
task-kind-specific reconcilable progress, server item filters, integrated operation evidence/logs
and native result-package export. `SQLiteTaskRepository.list_items` supports cursors without item
filters; its status-count helper is not a complete progress/effect projection. Operational logs
currently page a global population. The existing `PackageExchangeService.export_results` already
produces bounded, ordered, secret-free task result packages and must remain the export authority.

This is one coherent inspect-and-explain journey through the existing task engine. It supplies the
durable evidence needed by later control/recovery Tasks without implementing those commands or
creating a new task engine. High/T4 reflects interpretation of partial/uncertain effects, privacy
of joined evidence/export, consistent repository aggregation and any necessary additive migration.
Keep the existing bounded read/projection approach; do not add a generic reporting framework or
one Task per field, tab or command family.

Previous Task 42.1 B review (completed before replacing this file):

```text
Reviewed: f1806d3a13c0ab0538c07749ff82621782d91a24..ac5a43ed89d5d782809569ce5e58aedb8f2b03cb; completion report at cf7099a478a203f3f29ac57ef5b8acc295aadaa9
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

B inspected the full actual range and the third correction and independently verified the former
P1 through both real resource/media Files command APIs: new runs retain historical library/scope
and remain searchable. Admission display evidence commits with the Task; authority/execution is
unchanged. AC-T1–AC-T8 passed. Task 42.1's original contract/report remains in Git at the report SHA;
B's full final review copy is `/tmp/mediaflow-b-task42-1-pass.md`.

B independent evidence (logs `/tmp/mediaflow-b-r4-*`): Python full regression Ran 2060, OK
(skipped=7; 2053 passed); direct commands 60, transfers 100, inventory 39 and related integration/
release/migration/security 121 passed. Web original-command serial reruns passed 869 full / 453
focused; real Python-backed browser serial rerun passed 6. Docker release-security passed with
isolated daemon-visible TMPDIR, its resources cleaned; wheel smoke passed at schema 41. Python/Web
quality/build, governance, two example configs, Base..Head whitespace/private/dependency checks and
unchanged reference checksum passed. No implementation file was edited by B.

Preserved failure facts: first parallel Web runs were 865 passed / 4 failed full and 449 passed /
4 failed focused, followed by the unchanged complete serial passes above. First real-browser run
was 5 passed / 1 failed due to Playwright trace/artifact ENOENT from B's concurrent invocations
sharing output, then the original six cases passed serially. Required fake browser four-spec run
remained 58 passed / 2 failed (`deep-link.spec.ts:209` explicit route choice and `:479` V1 handoff).
B previously independently exported/built the complete immutable Task Base and reproduced exactly
these two errors (12 passed / 2 failed), log `/tmp/mediaflow-b-r3-base-deeplink.log`; original specs
and package/lockfile were unchanged. These two are proven pre-existing/unrelated, not claimed PASS.
No assertions, skips or timeouts were changed.

After PASS B reevaluated RO-1–RO-7: inventory/selection, unified current run/query/historical identity
and the read/privacy portion are delivered; RO-3 remains incomplete, RO-4's organize entry still
has an explanation/link gap, RO-5 lacks non-transfer safe queued Web Continue, and RO-6 lacks native
task-linked decisions/failed-analysis recovery. RO-7's future journey integration/restart proof is
still open. No Contract question awaits A; Slice Final is not authorized yet. The next coherent
unit is RO-3 rather than another inventory fix. Three correction rounds reused one bounded display
context/schema and existing authority, with no new engine; later Tasks must retain that simplicity.


## Implementation Scope

```text
Domain read/effect contracts → bounded Persistence queries and explicit durable links
→ shared Application projection/export → authenticated typed API → V2 panel/router/query → Tests
```

### Operator journey

- **Entry:** select an inventory row or open a supported run/Task/Job detail link in the shared shell.
- **Visible state:** historical identity, queue/Worker conditions, aggregate state, pipeline stages,
  known/unknown totals, reconciled item dispositions, durable effects and bounded explanations.
- **Action:** switch `任务详情` / `操作记录`, filter/page items and records independently, inspect one
  item's evidence, refresh and explicitly download the eligible task-scoped JSON result package.
- **Success:** the selected run and its items/results remain traceable before/after linkage,
  refresh/restart and Active changes; close/back returns to the same bounded inventory context.
- **Failure:** no Task yet, legacy missing evidence, unknown totals/effects, denied permission,
  unavailable/malformed/stale reads, missing pin and export failure stay distinct and actionable.
- **Recovery:** refresh the affected read, reset an invalid cursor/filter, restore the named
  prerequisite or follow an existing safe evidence/configuration destination. Reading/export never
  admits, continues, executes or retries media work; unknown effects remain investigation-only.

### Required behavior and boundaries

1. Extend the selected-run read boundary using persisted Job→Task/manual-execution/transfer links,
   never filename/time matching. Pending or failed pre-Task admissions have truthful queue/detail
   state and explicit item/evidence unavailability. Standalone Tasks and both library kinds' direct
   commands/transfers remain inspectable. Follow linkage without losing selected run/list context.
2. Define task-kind-specific progress from durable records. Separate aggregate state, pipeline stage,
   item disposition and Storage outcome. Unknown discovery totals remain indeterminate; known
   populations reconcile mutually exclusive pending/active/waiting/success/skipped/failed-partial/
   ignored/cancelled dispositions as applicable. Explain the unit and accounting basis. Keep scan
   errors and attachment/operation steps separate from primary-item counts. Analysis/Preview
   completion is not organize success; no invented current file, ETA or success percentage.
3. Fetch bounded independently paged/filterable items and operation records on the server. Reuse
   deterministic ordering and cursor conventions; bind new cursors to their exact run/task,
   submitted filters and principal context. Counts/aggregates cover the authorized population,
   not just the fetched page, and facts presented as one snapshot have a consistent read basis.
   Concurrent transitions and reads cannot fabricate progress or drop successful siblings.
4. Compose persisted item checkpoint, plan/Preview, Result and operation-step evidence through exact
   links. Explain available recognition/metadata identity, policies, target, operation/conflict,
   completed/pending/failed steps, cleanup and effect certainty. Label genuine legacy gaps as
   unavailable. Reuse existing stored analysis and redaction; never re-run Provider/planning/Storage
   to reconstruct history or use current Active as a historical fallback.
5. Query task-linked operational logs and bounded related persisted control/recovery audit evidence
   on the server; do not fetch the global collection and filter it in the browser or infer a link
   from text. Result/checkpoint truth remains independent of log presence. Existing global log,
   audit and recovery APIs remain compatible; missing old linkage is explicit unavailable evidence.
6. Integrate the existing result export behavior into the selected native detail. Server resolves
   the exact linked Task; package ordering, redaction, maximum limits, schema/digest and truncation
   remain truthful. Clearly label a bounded/truncated download. Missing export capability/evidence
   has a safe next action; a failed export never becomes an empty successful download.
7. Deliver reference-aligned Chinese `任务详情` / `操作记录` in the current right panel and complete
   narrow-screen detail, with keyboard/focus/return behavior. Preserve list filters, cursors,
   selection, tab and bounded item context through history, refresh and authentication continuation.
   Strict models reject malformed data; each failed read retains its own stale/unavailable state.
   Reuse bounded active/terminal/hidden-page polling and clear principal-owned data on auth change.
8. Preserve existing backend-advertised control paths and compatibility detail links. It is acceptable
   to retain existing controls or their safe destinations during this Task; no new Continue,
   Recognition/Metadata/Classification/conflict decision or failed-item admission is authorized.
   Explain durable blockers/effects from existing services without promising later capabilities.

Frozen: Slice Contract/Base, Roadmap, canonical requirements/Product Experience and reference images;
pipeline/rule semantics, physical source/Preview/execution authority, grants/tickets, queue/Worker
ownership, leases/fences, Storage adapters and OrganizerExecutor mutation behavior. Necessary
additive evidence/query/index persistence may be added only within this read journey, preserving
old pins/results/checkpoints/authority and never maintaining a second authoritative lifecycle.

## Acceptance Criteria

- [ ] **AC-T1 — Native exact detail:** selecting or deep-opening a run yields `任务详情` /
      `操作记录` in the existing shell, including pre-Task, linked, standalone and both-library
      work. Exact durable links survive Job→Task linkage and return/navigation; no manual joins.
- [ ] **AC-T2 — Reconcilable progress:** legal production Scan/Preview/Organize, direct commands,
      transfer and recovery-attempt records use their actual durable accounting basis. Beyond one
      page, known primary-item disposition totals reconcile; unknown totals are indeterminate.
      Concurrent active stages, waiting/ignored/skipped/partial/uncertain states, independent scan
      errors and attachments never become fabricated success or a universal completed-items ratio.
- [ ] **AC-T3 — Bounded independent queries:** item/record filters and cursor paging operate on the
      server, reject invalid/cross-run/filter/principal cursors and preserve siblings. Summary and
      presented totals remain page-independent and consistent under concurrent updates. No unbounded
      materialization, per-row Active resolution or browser merging of truncated collections.
- [ ] **AC-T4 — Durable explanations:** one item's available identity/policies/plan/result/steps,
      conflict/cleanup/effect certainty and exactly linked audit/log evidence are inspectable.
      Absent logs cannot erase a Result; legacy unavailable evidence is not invented. Restart,
      missing pin and Active rename/delete/root changes do not reinterpret known history.
- [ ] **AC-T5 — Scoped truthful export:** the native action downloads the existing eligible linked
      Task's secret-free JSON package, with truthful limit/order/truncation and verified package
      contract. Pre-Task/no-results/unavailable/denied/malformed/export failures are safe and visible.
- [ ] **AC-T6 — Complete presentation/recovery:** Chinese tabs, narrow/keyboard/focus, closed detail
      on entry, history/return, refresh/auth continuation and bounded polling preserve context.
      Loading, empty, stale, malformed, 401/403 and independent read failures offer meaningful next
      actions. A successful sibling stays visible when another item is blocked; unknown effects
      remain investigation-only. Existing Scan/Preview/Files/Task/Job/Automation links still work.
- [ ] **AC-T7 — Read safety/compatibility:** reads/filter/refresh/export create no media work, invoke
      no Provider or media Storage operations, backfill no historical state and grant no authority.
      Backend RBAC/redaction and cache isolation protect all joined paths, errors, logs and export.
      Existing control, retry/continuation, retired endpoints and C identity invariants survive.
- [ ] **AC-T8 — Reviewable tested delivery:** assigned T4 evidence, real Python-backed browser,
      package/static serving and any affected compatible migration pass with honest totals/skips/
      unavailable results. No private config, credentials, reference changes, unrelated files,
      removed coverage, weakened assertions or hidden skips enter the checkpoint.

## Required Tests

Use `.venv` or equivalent declared dependencies; Web commands run from `web/`. Tests use temporary
SQLite/storage and fake/local dependencies, never production credentials/media or remote services.
Record every actual attempt, command, failure, total, skip and unavailable gate. Preserve baseline
failures only with real independent attribution; do not relax assertions or hide skips.

### Focused and affected integration

Add `tests/test_operations_run_detail.py` (or an explicitly reported equivalent coherent suite)
covering AC-T1–AC-T5/AC-T7 through real SQLite/Application/API: legal producer/Worker links, pre-Task
and missing evidence, all current task-kind accounting, multiple pages, filtered item counts,
concurrent updates, principal/run/filter cursor binding, exact logs/audit linkage, result/export
truth, restart/pins, redaction and zero read side effects. Additive persistence requires a real
Task-Base schema fixture with unchanged pins/results/ownership/authority and fail-closed upgrades.

```sh
.venv/bin/python -m unittest discover -s tests -p test_operations_run_detail.py
.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py
.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py
.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py
.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py
.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py
.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py
.venv/bin/python -m unittest discover -s tests -p test_operational_logging.py
.venv/bin/python -m unittest discover -s tests -p test_configuration_package_exchange.py
.venv/bin/python -m unittest discover -s tests -p test_recovery_continuation.py
.venv/bin/python -m unittest discover -s tests -p test_recovery_batch.py
.venv/bin/python -m unittest discover -s tests -p test_api_security.py
```

Web model/query/router/component coverage must exercise independent tabs/pages/filters/failures,
truthful progress/effects, export, bounded polling, principal clearing and preserved return context.
Extend the existing real-Python browser harness for a real supported producer/Worker run→selected
detail→item/result evidence→scoped JSON download and history/restart, including partial/unknown
effects and zero side effects on reads. Fake responses supplement rather than replace this proof.

```sh
npm run test -- --run src/entities/operations src/features/operations src/shared/api src/routes
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

If adding a separate real detail spec, run it under the same Python configuration and report the
exact command. Run Playwright invocations sequentially because they share the artifact directory.

### T4 regression, quality, safety and packaging

```sh
python3 scripts/check_governance.py
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate
.venv/bin/python -m unittest discover -s tests -p test_release_security.py
.venv/bin/python -m unittest discover -s tests -p test_release_validation.py
.venv/bin/python -m unittest discover -s tests -p test_migration_rehearsal.py
.venv/bin/python -m unittest discover -s tests -p test_upgrade_preflight.py
git diff --check
git diff --check cf7099a478a203f3f29ac57ef5b8acc295aadaa9
sha256sum docs/pics/操作与任务.png
git check-ignore config/alist.json
git ls-files config/alist.json
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

Docker gate may use an isolated daemon-visible TMPDIR when required by the environment; record the
actual invocation/result and remove only gate-owned temporary resources. Unavailable is not PASS.
Reference SHA-256 stays `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`.
Private config must stay ignored/untracked/unstaged; forbidden-dependency search returns no matches.
Audit complete Base..Head/staged manifests without printing private configuration.

From `web/`:

```sh
npm run test -- --run
npm run typecheck
npm run lint
npm run format:check
npm run build
```

Build a wheel into an isolated temporary output directory with
`.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary-output>` and run
`.venv/bin/python scripts/wheel_smoke_test.py <built-wheel>`. Keep package/static and current schema
truth. Do not copy production config or modify reference/user files for a gate.

## Non-goals

- Work outside Slice 42, material Contract/architecture changes, Slice closure or next Slice.
- RO-4's new organize-entry journey, RO-5's new queued Continue/control authority and RO-6's new
  native review/failed-analysis commands. Preserve existing paths; report these remaining outcomes.
- Any retired direct-file retry/re-recognition/rematch/re-plan endpoint, automatic replay, new
  Provider/Storage operation, destructive authority, task engine or scheduler.
- Reconstructing legacy absent plans by running current policy/Provider/Storage, history deletion,
  universal rollback, required ETA, WebSocket/SSE, posters, dashboard/Automation/Notifications redesign.
- Optional proof, wording-only work or unrelated refactors promoted to separate Tasks.

## Developer Completion Report

### Changed Files

- Backend: `mediaflow/application/media_organizer.py`, `mediaflow/application/operations_lifecycle.py`, `mediaflow/infrastructure/sqlite_runtime.py`, `mediaflow/interfaces/service_api.py`.
- Browser proof: `scripts/operations_inventory_harness.py`, `web/tests/e2e/operations-inventory.python.spec.ts`.
- Web: `web/src/entities/operations/preview.ts`, `web/src/entities/operations/run-detail.ts`, `web/src/entities/operations/run-detail.test.ts`, `web/src/features/operations/RunDetailTabs.tsx`, `web/src/features/operations/RunDetailTabs.test.tsx`.
- Regression suites: `tests/test_operations_run_detail_plan_evidence.py`, `tests/test_operations_run_detail_log_isolation.py`.

### Implemented

- Run-item evidence joins `manual_execution_items` only by its exact persisted `(task_id, task_item_id)` link. It projects the captured Preview plan, analysis, identity, policies, destination, conflicts, cleanup plan and durable execution effects through bounded allowlists; absent links state that the reviewed plan is unavailable. Reads do not call a Provider, Planner or media Storage.
- Result cleanup status and step count are added only to the run-item evidence document, keeping existing Manual Preview/Execution response contracts intact. RecognitionType C stays C with Naming/Classification policy A.
- Operational logs now require the reusable `plan_id` plus persisted Task or Job linkage. The Organizer stamps its Task ID when emitting tracked logs; no time or message inference attributes legacy unlinked logs.
- Web detail preserves and renders evidence-section contents and the captured reviewed plan, effects and cleanup outcome. The Python-backed harness now admits an exact Preview through the real API and completes it with `ManualOrganizeExecutionWorker` using temporary managed configuration, Local Storage and synthetic metadata.

### Tests and Results

- Final Python regression: `.venv/bin/python -m unittest discover -s tests` — **PASS**, 2,113 tests, 7 skipped. The earlier correction attempt failed one `test_manual_operations_contract` fixture comparison after broadening shared Manual API documents; I scoped the new fields to run-item evidence, reran that exact fixture test successfully, then reran the full suite successfully.
- `.venv/bin/python -m unittest tests.test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_match_the_frontend_fixture` — first **FAIL** with that intermediate broad projection, then **PASS** after restoring the existing Manual API shape.
- Focused run-detail/log-isolation tests after that correction: `.venv/bin/python -m unittest tests.test_operations_run_detail tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation` — **PASS**, 53 tests. The two new suites contain 10 plan-evidence and 7 log-isolation tests.
- These focused integration commands passed (449 tests total); the final full Python regression above covers them again on the final source:
  - `.venv/bin/python -m unittest discover -s tests -p test_operations_run_detail.py` — **PASS**, 36.
  - `.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py` — **PASS**, 39.
  - `.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py` — **PASS**, 20.
  - `.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py` — **PASS**, 13.
  - `.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py` — **PASS**, 19.
  - `.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py` — **PASS**, 37.
  - `.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py` — **PASS**, 60.
  - `.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py` — **PASS**, 100.
  - `.venv/bin/python -m unittest discover -s tests -p test_operational_logging.py` — **PASS**, 6.
  - `.venv/bin/python -m unittest discover -s tests -p test_configuration_package_exchange.py` — **PASS**, 13.
  - `.venv/bin/python -m unittest discover -s tests -p test_recovery_continuation.py` — **PASS**, 28.
  - `.venv/bin/python -m unittest discover -s tests -p test_recovery_batch.py` — **PASS**, 48.
  - `.venv/bin/python -m unittest discover -s tests -p test_api_security.py` — **PASS**, 13.
- Web focused command `npm run test -- --run src/entities/operations src/features/operations src/shared/api src/routes` — **PASS**, 33 files / 518 tests. Full Web command `npm run test -- --run` — **PASS**, 61 files / 936 tests. `npm run typecheck`, `npm run lint`, `npm run format:check` and `npm run build` — **PASS**; build retains the existing large-chunk warning.
- Fake-response Playwright command `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts` — **63 passed / 2 failed**. The failures are `deep-link.spec.ts:209` and `:479`; B independently reproduced both at Task Base and recorded them as pre-existing/unrelated. The real Python-backed command `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` — **PASS**, 11 tests, including real admission/Worker completion, C identity with A policies, completed CREATE_DIRECTORY/MOVE, disabled cleanup, scoped export and restart-persistent detail.
- Earlier overlapping Web attempts exposed one Manual Organize intent timeout and two Storage page assertions before being interrupted; the isolated intent test and both final serial Web suites passed. The first Python-browser attempts exposed two harness startup issues and a Worker snapshot mismatch (10/11); after fixing the import/config path and pinning the Worker to the Active snapshot, the exact final Python-browser command passed 11/11.
- T4 checks — **PASS**: `python3 scripts/check_governance.py`; `.venv/bin/python scripts/docker_release_security_smoke_test.py` (temporary project and context cleaned); `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`; `.venv/bin/python -m compileall -q mediaflow tests scripts`; `.venv/bin/python -m pip check`; both required `config validate` commands; release security (6), release validation (3), migration rehearsal (6) and upgrade preflight (4) tests. `git diff --check` and `git diff --check cf7099a478a203f3f29ac57ef5b8acc295aadaa9` are clean. Reference image SHA-256 matches `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`; `config/alist.json` is ignored and neither tracked nor staged; `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` found no matches.
- Wheel gate: `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary-output>` and `.venv/bin/python scripts/wheel_smoke_test.py <built-wheel>` — **PASS**, schema 42, with no migration required.

### Decisions

- Reused the persisted Manual execution-item link and reviewed `plan_json`; made the log query require the exact run linkage alongside `plan_id`.
- Kept the new Result cleanup facts and cleanup plan projection local to run-item evidence so existing Manual Preview/Execution documents do not change.
- Used only temporary local paths and a synthetic provider in the browser harness. No migration or production service was needed.

### Remaining In-Slice Work

RO-4's new organize-entry journey, RO-5's queued Continue/control authority and RO-6's native review/failed-analysis commands remain outside this Task.

### Risks / Deviations

- The two deep-link Playwright failures remain as the Base-proven, unrelated failures noted above. The Vite build emitted a large-chunk warning. The Python suite emits existing SQLite `ResourceWarning`s but completed successfully.
- Preserved the three pre-existing untracked images under `docs/pics/`; they are not part of this checkpoint. No external service gate was unavailable.

### Checkpoint

Status: READY FOR B REVIEW
Head SHA: 186e61f850be69126997c948f544146c1198e78e

## B Review Result

```text
Reviewed: cf7099a478a203f3f29ac57ef5b8acc295aadaa9..4edc41534ea767b72ad0b217ff66bf9ba1ec381c
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — 原生条目证据没有完成持久解释旅程（AC-T4；Scope 4；Slice RO-3 / AC-6）。**
  当前合法入口是 ResourceLibrary Files 整理 → 已审核 Preview → 明确执行 → Worker 完成
  → `操作与任务` 选中运行 → `查看证据`。B 使用已通过 Storage check / strategy test /
  destination precheck 并 checked activation 的真实 Managed 配置、SQLite FileIndex/Task、
  原有完整能力的 LocalStorage 和本地合成 MetadataProvider，经过真实 API 准入和
  `ManualOrganizeExecutionWorker` 完成一项 MOVE；未手工补写 TaskItem、Result 或分析证据。
  `.venv/bin/python /tmp/mediaflow-b-t42-2-managed-detail.py` 与
  `node /tmp/mediaflow-b-t42-2-managed-browser.mjs` 可重复该旅程。持久 Result 的
  `recognition_type=C`、`metadata_policy_id=C`、Naming/Classification/Organize policy A、
  `completed_operations=[CREATE_DIRECTORY, MOVE]` 均存在，checkpoint 还有
  `cleanup_status=disabled`；原生详情未展示这些身份、策略、步骤，并把清理显示为 `—`。
  同一执行精确关联的持久 Preview GET 返回 200，含 recognition/metadata/naming/
  classification 分析、operationPolicy 和 conflicts；新条目证据却返回 `evidence=[]`，
  Web 显示“该条目没有持久化的计划/分析证据”。`操作记录` 只有摘要，`查看条目` 回到同一
  不完整详情。证据在 `/tmp/mediaflow-b-t42-2-managed-evidence.json`、
  `/tmp/mediaflow-b-t42-2-managed-persisted-preview.json` 和
  `/tmp/mediaflow-b-t42-2-managed-browser.json`。实际代码位于
  `service_api.py::_operations_run_item_evidence`、
  `run-detail.ts::normalizeEvidenceDocument`（丢弃 section 内容）和
  `RunDetailTabs.tsx::RunEvidenceSection`（只显示段名/摘要）。修正方向：复用已有持久
  Manual execution→Preview/item 关联及安全解释投影，在同一有界只读旅程展示适用的身份、
  策略、计划/冲突、已完成/未确认步骤与清理；真正缺失才标 unavailable，不重跑 Provider、
  Planner 或 Storage。补足现有真实 Python 浏览器用例的生产准入/Worker→详情解释验证，
  不能仅靠仓库补写的 rich fixture 或断言段名证明完成。
- **P1 — “精确关联日志”混入另一运行的记录（AC-T4；Scope 5；Slice RO-3 / AC-6）。**
  在同一 checked-active Managed 配置及完整 LocalStorage 上，当前生产
  `PersistentTaskCoordinator` / `MediaOrganizerService` / `OrganizerExecutor` /
  `SQLiteOperationalLogger` 对同一合法源先后执行两次零变更 Preview，得到两个独立 Task。
  `.venv/bin/python /tmp/mediaflow-b-t42-2-log-link.py` 返回两项相同的确定性
  `plan_id=4b79249fb44270c6f5f1`；第一项的
  `GET /api/v1/operations/runs/{taskA}/items/{itemA}` 返回 4 条日志，其中 2 条由第二次
  运行实际生成，证据在 `/tmp/mediaflow-b-t42-2-log-link.log` 与
  `/tmp/mediaflow-b-t42-2-log-link.json`。操作员查看第一项任务证据时，另一运行的时间和
  execution/plan 事件被标成该项的“精确关联日志”，无法正确区分两次尝试。
  `organizer.py::_plan_id` 只哈希源/目标 Storage 与路径，不是运行唯一键；新增
  `SQLiteTaskRepository.list_operational_logs_for_plan` 仅按 plan_id 查询，API 未附加
  当前 Task/Job 边界。修正方向：在现有有界查询上同时约束该运行的真实持久 Task/Job
  关联和计划，不能仅凭可复用 plan ID 归属日志；没有足够运行关联的历史日志明确不可用，
  不按时间/文本猜测或补写关联。加入两次真实生产 Preview 的隔离回归，保持 Result 独立
  于日志，不改变任务引擎、执行权限或媒体行为。
