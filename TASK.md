# Task 42.2 — Native run detail, progress and operation evidence

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.2
Parent Slice: 42
Status: PLANNED
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

Backend: `mediaflow/interfaces/pagination.py` (new scoped cursor kinds);
`mediaflow/domain/operations_run.py` (dispositions, progress/record/item-window
contracts); `mediaflow/domain/task_persistence.py` (`list_items` status filter);
`mediaflow/infrastructure/sqlite_runtime.py` (schema 42 additive read indexes,
`operations_run_with_progress`, `operations_run_items_window`,
`operations_run_records_window`, `resolve_operations_run_link`,
`list_operational_logs_for_plan`, filtered `list_items`);
`mediaflow/application/operations_lifecycle.py` (accounting basis, progress/
record/item-evidence documents); `mediaflow/application/automation.py` (documented
worker schema default 41→42); `mediaflow/interfaces/service_api.py`
(`runs/{id}` overview now carries `progress`; `runs/{id}/items`,
`runs/{id}/records`, `runs/{id}/items/{itemId}`, `runs/{id}/export`; scoped
cursor scopes; masked audit routes for the run family).

Web: new `web/src/entities/operations/run-detail.ts`,
`web/src/features/operations/run-detail-query.ts`, `run-detail-state.ts`,
`RunDetailTabs.tsx`; extended `run.ts`, `task.ts` (exported item/result
normalizers), `api-client.ts` (fetchers), `OperationsLanding.tsx`,
`TaskDetailPage.tsx` (native tabs replace the separate item/result tables),
`destination-model.ts` (auth-continuation allowlist), `styles.css`.

Tests: new `tests/test_operations_run_detail.py` (36), `run-detail.test.ts` (32),
`run-detail-state.test.ts` (4), `RunDetailTabs.test.tsx` (8), extended
`operations-api.test.ts` (+13), `OperationsInventory/OperationsRouter` tests,
`destination-model.test.ts` (+2); `scripts/operations_inventory_harness.py` rich
durable population through real repository write paths;
`web/tests/fake-server.mjs` detail routes; `web/tests/e2e/operations.spec.ts`
(+5 detail tests incl. a real download), `operations-inventory.python.spec.ts`
(+4 real-Python detail tests). Six existing schema-version pins updated
41→42 as factual migration maintenance.

### Implemented

AC-T1–AC-T8 of the Task. One selected-run journey: the overview and its
task-kind-specific progress come from one SQLite read snapshot (mutually
exclusive dispositions reconcile to the known total; a live scan or an
unadmitted Task stays honestly indeterminate; admitted-but-unmaterialized rows
publish inside `pending`; success splits exactly into confirmed plus uncertain,
and uncertain effects are never counted as confirmed success; scan errors and
attachment steps stay separate; no ETA/current-file/success-percentage). Items
and operation records page and filter on the server with cursors bound to
principal + exact run/task + submitted filters (new `run_items`/`run_records`
scoped kinds; legacy unscoped cursors and routes untouched). The record stream
unions `task_results`, captured `pipeline_evidence`, operational logs joined by
persisted `task_id`/`job_id`, and control/recovery audit rows joined by
persisted task IDs — never text, never the global collection filtered in the
browser. One item's evidence composes checkpoint/Results/plan/plan-linked logs
through exact IDs; a foreign item is a 404; absent logs never erase a Result;
configuration digests/fingerprints stay out. The native export action resolves
the run's exact linked Task server-side and delegates to the existing
`PackageExchangeService.export_results` authority (ordering/redaction/limits/
digest/truncation unchanged; pre-Task is an explicit 409 `task_not_linked`;
a failed export never becomes an empty download; the downloaded
`mediaflow.results.v1` camelCase package is validated before saving). Chinese
`任务详情`/`操作记录` tabs, narrow-screen detail, focus/Escape/return behavior,
URL-owned tab/filters/cursors/inspected-item context through history, refresh
and auth continuation, shared bounded polling that settles on terminal state.
All reads are GET-only side-effect-free; existing Task/Job/Files/Scan/Preview/
Automation links, controls and retired-endpoint boundaries survive; RecognitionType
C identity is preserved through every joined path and the export. Additive
schema-42 indexes only, with a real Task-Base (schema-41) upgrade proof.

### Tests and Results

Focused + affected integration (`.venv/bin/python -m unittest discover -s tests -p <file>`, all OK):
`test_operations_run_detail.py` 36; `test_operations_run_inventory.py` 39;
`test_operations_workspace.py` 20; `test_task_persistence.py` 13;
`test_processing_worker_readiness.py` 19; `test_v2_manual_organize.py` 37;
`test_direct_file_operations.py` 60; `test_direct_file_transfers.py` 100;
`test_operational_logging.py` 6; `test_configuration_package_exchange.py` 13;
`test_recovery_continuation.py` 28; `test_recovery_batch.py` 48;
`test_api_security.py` 13.

Full regression: `discover -s tests` → Ran 2096, **OK (skipped=7)** (run twice,
including after the final source state).

T4 gates: `scripts/check_governance.py` PASS; `ruff format --check` +
`ruff check` clean; `compileall` OK; `pip check` OK; both example configs
`config validate` OK; `test_release_security.py` 6 OK,
`test_release_validation.py` 3 OK, `test_migration_rehearsal.py` 6 OK,
`test_upgrade_preflight.py` 4 OK; `git diff --check` (worktree and
`cf7099a`) clean; reference SHA-256 unchanged
`a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`;
`config/alist.json` ignored/untracked/unstaged, `git ls-files` empty;
`grep -rn -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` → 0 matches.
Docker gate: first invocation **FAILed environmentally** (the daemon cannot see
this container's private `/tmp` tmpfs: "bind source path does not exist");
re-run per the Task's allowance with an isolated daemon-visible
`TMPDIR=/root/mediaflow/.gate-tmp` → "Release-security smoke acceptance
passed" (re-verified after the final formatting); only gate-owned temp removed.
Wheel: `pip wheel . --no-deps --no-build-isolation -w <temp>` +
`wheel_smoke_test.py` → PASS at schema 42 (rebuilt and re-run on the final
state).

Web (from `web/`): `npm run test -- --run` → 61 files, **922 passed** (final;
869 before this Task's added coverage); `npm run typecheck`, `npm run lint`,
`npm run format:check`, `npm run build` all pass. Playwright invocations were
run sequentially (shared artifact directory):
`npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts
tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts` →
**63 passed / 2 failed**; both failures are `deep-link.spec.ts:209` (explicit
route choice) and `:479` (V1 handoff) — the same two B independently proved
pre-existing/unrelated at this Task's Base (log
`/tmp/mediaflow-b-r3-base-deeplink.log`, 12 passed / 2 failed on the unmodified
Base export). They are recorded as **FAIL / PRE-EXISTING / UNRELATED**, not
claimed PASS; no assertions, skips or timeouts were changed.
`npm run test:e2e -- --config=playwright.python.config.ts
tests/e2e/operations-inventory.python.spec.ts` → **10 passed**, including the
new real-producer journey: selected detail → truthful organize progress (已处理
5/6, confirmed vs uncertain split) → server item filter → item evidence →
exactly-linked records stream with kind filter → real `mediaflow.results.v1`
download with digest/ordering/truncation checks → GET-only proof for every
detail read → indeterminate run states 总数未知 → tab/filter context survives a
reload through auth continuation.

### Decisions

- New scoped cursor kinds `run_items`/`run_records` (principal + exact run/task +
  submitted filter bound) instead of re-scoping `task_items`/`task_results`, so
  the V1 compatibility detail and its existing cursors stay byte-compatible.
- The progress partition is derived from persisted item statuses (so it always
  reconciles); the uncertain-effect annotation is published as
  `confirmed_success` + `uncertain_success` (sum equals the success status count)
  and the UI headlines confirmed success only — uncertain is never claimed as
  success while reconciliation holds.
- Indeterminate rule: a live manual Scan (discovery not reconciled), a
  non-terminal Task with nothing admitted, or an unknown/legacy status row (it
  counts as failed/partial, never dropped).
- The record stream uses prefixed record IDs (`result:`/`evidence:`/`log:`/
  `audit:`) as the deterministic keyset tiebreak, with a bounded two-phase
  payload fetch inside the same snapshot.
- Export stays delegated to `PackageExchangeService.export_results`; the route
  adds only run→Task resolution. The frontend validates the committed
  camelCase interchange row contract (a real snake/camel mismatch was caught by
  the real-browser proof and fixed in the frontend validator, not the package).
- Schema 42 is index-only and additive; the six test pins and the documented
  `ProcessingWorkerService` default were updated exactly as previous bumps did.
- The landing overview read now passes through `AuthorizedReadBoundary` so
  401/403/unavailable/malformed overview failures stay distinct instead of
  sticking on loading.
- The Python harness attaches the repository-only `PackageExchangeService`
  (test-only wiring; configuration-dependent package routes keep their 503).

### Remaining In-Slice Work

Per B's post-42.1 evaluation, still open in Slice 42 and untouched here:
RO-4's new organize-entry journey completion, RO-5's non-transfer safe queued
Web Continue, RO-6's native task-linked decisions/failed-analysis recovery, and
RO-7's remaining future-journey integration/restart proof. Existing controls and
their safe destinations were preserved, not extended.

### Risks / Deviations

- The two `deep-link.spec.ts` failures above are pre-existing/unrelated
  (B-proven at Base); this Task did not touch those specs.
- The Docker gate required the Task-allowed isolated daemon-visible `TMPDIR` in
  this environment; recorded above with the passing re-run.
- The V1 compatibility route `/api/v1/tasks/{id}` still publishes
  `configuration_snapshot_digest` in its pre-existing compatibility document
  contract; every new bounded surface (overview/items/records/evidence/export)
  publishes no digest or fingerprint (asserted).
- Full-suite output contains pre-existing ResourceWarnings about unclosed temp
  SQLite connections from older tests; no failures, no skips added.
- B's rewritten `TASK.md` (this Task's contract) travels with the completion
  report commit; the implementation checkpoint itself contains no Task-document
  churn.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 4edc41534ea767b72ad0b217ff66bf9ba1ec381c

## B Review Result

```text
Reviewed: NOT REVIEWED
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
