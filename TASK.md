# Task 42.1 — Unified run inventory and selected-run overview

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.1
Parent Slice: 42
Status: READY FOR B REVIEW
Task Base: f1806d3a13c0ab0538c07749ff82621782d91a24
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authenticated operator opens `操作与任务`, finds an admitted or historical run using truthful
server-side search, filters, counts and paging, then opens that run's overview without joining Jobs
and Tasks manually. Complete the inventory/selection journey in RO-1 and RO-2 and the read/privacy
portion of RO-7. This Task does not claim the whole Slice or RO-3 through RO-6 complete.

## Why This Task Exists

At Task Base, `OperationsLanding.tsx` is a Worker/manual-action/navigation hub. `TaskListPage.tsx`
and `JobListPage.tsx` read separate bounded collections. `SQLiteTaskRepository.list_tasks` and
`list_jobs` support status/command filters, but not a unified population, business-name/safe-scope
search, creation-time filters or unified totals. `AutomationJob.task_id` and manual execution/task
links already provide durable relationship evidence. Existing lifecycle projections protect reads
and controls, but are not a unified run inventory.

Building only the table would either double-count linked work or require browser merging of
truncated collections. This Task completes a vertical read journey, including durable historical
display evidence and authoritative repository queries. It does not replace the processing engine.
The remaining Slice work can be grouped into coherent detail/evidence, organize-entry,
lifecycle-continuation and task-recovery units; there is no reason now to split into more than eight
Tasks. These are sizing observations, not pre-created Tasks or changes to the Contract.

B planning evidence: committed Slice/Roadmap ACTIVE and governance PASS at Task Base;
`.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py` passed 20 tests.
That establishes the existing Operations baseline, not acceptance of this planned feature.

## Implementation Scope

```text
Domain read contracts → Persistence/query and admission display evidence
→ shared Application projection → authenticated API → typed Web/query/router → Tests
```

### Operator journey

- **Entry:** `/ui-v2/operations` in the existing AppShell, or an explicit supported run detail link.
- **Visible state:** Chinese business names, operation kind, historical source/target scope,
  trigger, aggregate state, times and bounded queue/Worker evidence; trustworthy result counts.
- **Action:** submit text/status/kind/time filters, click a count card, page, refresh, select/close
  a run and follow existing Task/Job/execution detail for further evidence.
- **Success:** an explicitly linked run remains discoverable before and after Task creation,
  is counted once, and opens with historical identity and list context intact.
- **Failure:** no work, no matches, forbidden access, unavailable/malformed/stale data, missing
  historical evidence and unavailable Worker are distinct; a failed read never means zero runs.
- **Recovery:** correct/reset filters or cursor, retry the bounded read, reconnect, or follow the
  named readiness prerequisite. Refresh/reconnect/navigation never admits or replays work.

### Required behavior and boundaries

1. Add a shared read projection over explicit durable Job/Task/manual-execution relationships.
   Preserve an admission's visible identity and detail links when it acquires a Task. Standalone
   Tasks and pre-Task pending/failed Jobs remain visible. Distinct occurrences, retries and recovery
   continuations remain independent attempts with existing links. Never infer links from filename,
   creation-time proximity, labels or a command prefix alone.
2. Derive status from actual queue/processing evidence. Completed Jobs cannot hide linked Task
   failure/partial success. Waiting, paused, queued and unknown evidence remain distinguishable;
   attention is an overlapping facet. Projection is not a new lifecycle or execution authority.
3. Implement bounded deterministic repository queries for text over safe business name/scope,
   status, operation kind and creation-time range. Support combined filters and directional cursors
   bound to query and principal/authorization context. Obtain page, filtered total, partitioned
   status counts and overlapping attention count from a consistent read basis of the same authorized
   filtered population. Label the population and card-click filter behavior. Do not load all records
   into Python/the browser or resolve an unbounded number of pins per read.
4. Supply bounded historical context from durable admission evidence or the exact pinned snapshot.
   Add only display/link persistence and indexes needed for query correctness and bounded cost.
   Capture necessary evidence for new supported admissions using shared producers; do not change
   selection, authorization, claim or execution behavior. Equal ResourceLibrary/MediaLibrary IDs
   remain distinct. Active rename/delete/root changes cannot rewrite known historical labels.
   Missing legacy evidence is explicitly unavailable; no fallback to current Active or read-time
   backfill of historical records.
5. Expose authenticated bounded list and selected-run overview through shared Python read ports
   (a `/api/v1/operations/runs` family is suitable). Durable history remains readable without usable
   current Active. Reuse existing safe lifecycle/readiness projections and exact linked detail
   routes; do not advertise a newly supported command.
6. Replace the Operations hub body with reference-aligned cards, compact filters, full-width table
   and explicitly selected overview panel. Entry has no selection; selection opens the right panel,
   with complete narrow-screen detail and accessible return. Show actual business identity/scope/
   trigger/state/times/readiness and links to deeper existing evidence. Keep Scan/Preview discoverable
   and existing Task/Job/Automation/Notification navigation and detail/control journeys usable.
7. Use strict frontend models and central API/query/auth boundaries. Preserve submitted filters and
   bounded paging/selection context through history, close/back, deep links, refresh and auth
   continuation. Poll bounded active-work reads, pause hidden polling, back off after failure and
   settle terminal detail polling. Label retained stale data and clear principal-owned cache/
   selection on authentication changes.

Frozen: Slice Contract/Base, Roadmap, canonical requirements/Product Experience, reference images,
rule semantics, physical source/plan authority, execution grants/tickets, Storage adapters,
OrganizerExecutor and Worker ownership/claim/mutation behavior. Existing producers may gain only
necessary display/link evidence. A narrowly necessary architecture factual update may describe the
read boundary and distinguish delivered portions from remaining TARGET; it may not redefine
architecture contracts or claim whole-Slice completion.

## Acceptance Criteria

- [ ] **AC-T1 — One real population:** legal production admissions remain visible before/after Task
      creation without duplication or identity/link loss. Standalone Tasks, pre-Task failures,
      manual executions, scheduled occurrences, continuations and both library kinds' existing
      direct commands/transfers are discoverable. Unknown legacy commands get bounded honest labels.
      Job completion cannot mask Task partial/failure.
- [ ] **AC-T2 — Authoritative query/counts:** text/status/kind/time filters compose; invalid values,
      ranges and limits reject safely; ties page deterministically. Filter/principal cursor mismatch
      refuses with read recovery. Totals and status partitions reconcile beyond one page; attention
      is explicitly overlapping. Page/counts share one read basis under concurrent linkage/state
      changes. The browser never merges truncated lists or manufactures totals/pages.
- [ ] **AC-T3 — Historical identity/privacy:** business name, trigger and source/target scope derive
      from admitted/pinned evidence or explicit unavailability. New admissions retain needed context;
      restart and Active A-to-B rename/delete/root changes cannot rewrite A's identity/search results.
      Equal library IDs retain kinds. Public data/search/errors expose no secrets, private endpoints,
      host roots or raw adapter exceptions.
- [ ] **AC-T4 — Complete find/inspect journey:** shared-shell Chinese inventory follows reference
      composition using real data/type icons. Default entry is full-width with closed detail;
      mouse/keyboard selection and supported deep entry open the correct overview. Close/back/history/
      refresh/reconnect retain safe list context; narrow view is complete. Existing Task/Job/execution
      links remain meaningful after linkage; Scan/Preview and existing journeys remain functional.
- [ ] **AC-T5 — Honest states/failures:** overview distinguishes aggregate status, queue/Worker
      readiness and acknowledged pause from a request. Do not turn `completed_items` into organize
      success or invent percentages/ETA; display known durable facts or explicit unknown/indeterminate
      state. No-work/no-match/loading/stale/read failure/malformed/401/403 offer safe next actions.
      Unavailable is not zero. Active/terminal/hidden/failure polling never replays commands.
- [ ] **AC-T6 — No new authority or side effects:** new reads are authorized/bounded, create no
      processing/admission/configuration work, invoke no Provider or media Storage calls, and do not
      write display backfills. Existing control/mutation rules and C identity under A reuse survive.
- [ ] **AC-T7 — Durable compatible delivery:** additive persistence migrates a real Task-Base schema
      fixture without rewriting pins, links, results, checkpoints or authority. Restart retains truth;
      unsupported schema fails closed; packaged Python static serving loads the built UI. Focused
      integration, real Python-backed browser evidence, full regression and applicable T4 gates pass
      with actual totals/skips/unavailable evidence recorded.
- [ ] **AC-T8 — Reviewable checkpoint:** report actual Base..Head manifest, tests/results, decisions
      and remaining Slice gaps. No private config/credentials, reference changes, unrelated files,
      removed coverage, weakened safety assertions or concealed skips enter the checkpoint. B Review
      stays PENDING until B inspects implementation.

## Required Tests

Use `.venv` or an equivalent declared-dependency environment; run Web commands from `web/`.
Record exact commands, results, totals, skips, failures and unavailable gates. An unavailable
required gate is not PASS. No production media, credentials or external service is required.

### Focused and affected evidence

Add `tests/test_operations_run_inventory.py` covering real SQLite/Application/API integration:
AC-T1–AC-T3 and AC-T6–AC-T7, multiple pages/ties/combined filters/counts, concurrent Job→Task linkage
and state changes, command families, exact pins/missing legacy evidence, both library kinds,
restart, denied permissions/cursors, redaction and zero Provider/Storage/work side effects. If
persistence changes, include a Task-Base schema upgrade fixture, failure/reopen and preserved
execution/Worker state. Use current legal production assemblies; tests cannot remove supported
production capabilities to manufacture a failure or establish completeness.

```sh
.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py
.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py
.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py
.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py
.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py
.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py
.venv/bin/python -m unittest discover -s tests -p test_api_security.py
```

Add Web inventory model/query/router/component coverage beside existing Operations tests: malformed
response rejection, server filters/cursors/card actions, selection/history/close/deep links,
authentication clearing, independent read failures and polling lifecycle. Run:

```sh
npm run test -- --run src/entities/operations src/features/operations src/shared/api src/routes
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts
```

Adapt existing browser expectations only for intentional inventory presentation/navigation changes;
preserve their safety/compatibility assertions. Add an isolated real Python API/SQLite browser
harness/spec, for example `playwright.python.config.ts` and
`tests/e2e/operations-inventory.python.spec.ts`, and run:

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

Use the built artifact, actual Python services, temporary DB/storage and fake/local dependencies.
Prove admission→Task linkage through a real supported producer/Worker, stable counts, filtered
selection/return, Worker waiting, historical identity after restart/Active change and side-effect-free
reads. Fake HTTP fixtures are additional UI evidence, not a substitute. Equivalent harness naming
is allowed; report its exact reproducible command.

### T4 full regression and quality/safety/package gates

```sh
python3 scripts/check_governance.py
scripts/docker_release_security_smoke_test.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate
git diff --check
git diff --check f1806d3a13c0ab0538c07749ff82621782d91a24
sha256sum docs/pics/操作与任务.png
git check-ignore config/alist.json
git ls-files config/alist.json
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

Reference checksum: `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`.
Private config must be ignored and absent from tracked/staged files; forbidden-dependency `rg`
must have no matches (exit 1). Inspect exact Base..Head and staged manifests/diffs for private or
unrelated files without printing private configuration contents.

From `web/`:

```sh
npm run test -- --run
npm run typecheck
npm run lint
npm run format:check
npm run build
```

Packaging/static-serving and migration gates:

```sh
.venv/bin/python -m unittest discover -s tests -p test_release_security.py
.venv/bin/python -m unittest discover -s tests -p test_release_validation.py
.venv/bin/python -m unittest discover -s tests -p test_migration_rehearsal.py
.venv/bin/python -m unittest discover -s tests -p test_upgrade_preflight.py
```

Build a wheel into an isolated temporary output directory using
`.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary-output>` and run
`.venv/bin/python scripts/wheel_smoke_test.py <exact-built-wheel>`; record substituted exact paths.
Slice-final resident continuation, destructive recovery and Docker lifecycle evidence remain
required at applicable implementation/final boundaries. This inventory Task does not claim those
not-yet-implemented outcomes.

## Non-goals

- New control/Continue commands, Worker claim/execution changes, authority reissue or unsafe replay.
- Full RO-3 task-kind progress, independently paged item/step/result records, task-scoped logs/audit
  and export presentation; retain existing deeper detail/evidence access in this Task.
- Completing RO-4 live-file `新建整理任务`/return flow or redesigning Files/Preview/execution.
- RO-6 Recognition/Metadata/Classification/conflict forms and failed-analysis recovery.
- Anything Explicitly Deferred/Excluded by Slice 42, including global Review, history deletion,
  queue replacement, MediaLibrary organization, posters, fabricated ETA or reference image changes.
- Canonical documentation closure, Roadmap changes, next-Task creation or Slice PASS/CLOSED.
- Optional copy polish, P2 cleanup or unrelated refactors.

## Developer Completion Report

### Changed Files

Implementation checkpoint `e89db7c` — Base..Head `f1806d3..e89db7c`, 32 files,
5527 insertions / 318 deletions (`git diff --check` clean; no private or
unrelated files, reference images untouched):

- Python domain/persistence/API: `mediaflow/domain/operations_run.py` (new),
  `mediaflow/infrastructure/sqlite_runtime.py`, `mediaflow/interfaces/service_api.py`,
  `mediaflow/interfaces/pagination.py`, `mediaflow/application/automation.py`.
- Python tests: `tests/test_operations_run_inventory.py` (new, 27 tests);
  schema pins 39→40 in `tests/test_configuration_classification.py`,
  `tests/test_configuration_destination.py`,
  `tests/test_configuration_destination_activation.py`,
  `tests/test_configuration_destination_precheck.py`,
  `tests/test_configuration_organize.py`, `tests/test_resident_correction.py`.
- Harness: `scripts/operations_inventory_harness.py` (new),
  `web/playwright.python.config.ts` (new), `web/playwright.config.ts`
  (python-spec exclusion).
- Web source: `web/src/entities/operations/run.ts` + `run.test.ts` (new),
  `web/src/shared/api/api-client.ts`, `web/src/shared/api/operations-api.test.ts`,
  `web/src/features/operations/run-query.ts` (new),
  `web/src/features/operations/OperationsLanding.tsx`,
  `web/src/features/operations/OperationsInventory.test.tsx` (new),
  `web/src/features/operations/ManualOperationsRouter.test.tsx`,
  `web/src/shared/navigation/destination-model.ts` + test,
  `web/src/shared/ui/styles.css`.
- Web e2e: `web/tests/fake-server.mjs` (runs endpoints),
  `web/tests/e2e/operations.spec.ts` (+2 inventory journeys),
  `web/tests/e2e/operations-inventory.python.spec.ts` (new, 5 tests), and
  intentional presentation adaptations in `web/tests/e2e/manual-operations.spec.ts`,
  `web/tests/e2e/manual-organize.spec.ts`, `web/tests/e2e/medialib-transfers.spec.ts`.

### Implemented

RO-1/RO-2 vertical read journey, end to end:

- **One real population.** A unified run inventory over `automation_jobs ∪
  standalone tasks`, joined only by the explicit persisted
  `automation_jobs.task_id` (never filename/time/labels/command prefix). A Job
  keeps its admission identity before and after acquiring a Task and is counted
  once; pre-Task pending/failed Jobs, standalone Tasks (manual scans, exact
  manual organize executions, direct commands/transfers), scheduled definition
  occurrences and retry/recovery continuations are all discoverable. Unknown
  legacy commands keep an honest `recognizedCommand: false` label instead of a
  guessed business meaning. A completed Job never masks its linked Task's
  partial success/failure (aggregate-status precedence in SQL mirrors
  `derive_run_status`).
- **Authoritative query/counts.** `GET /api/v1/operations/runs` supports
  composed text/status/kind/creation-time filters, deterministic directional
  cursors (kind `operations_runs`, always scope-bound to the submitted filters
  *and* the reading principal — cross-filter or cross-principal replay refuses
  with `invalid_request`), and returns page + filtered total + partitioned
  status counts + the explicitly overlapping attention count from one
  lock-held consistent read basis. Invalid values/limits/ranges reject with 400.
- **Historical identity/privacy.** Scope evidence comes from durable
  admission rows only (`task.scope_path`, then the Job's recorded admission
  scope), published through `bounded_identity_path` (relative identity only;
  absolute host roots become the redaction marker); missing legacy evidence is
  `null`/explicitly unavailable with no current-Active fallback and no
  read-time backfill. Reads skip the Active binding refresh (like
  `/api/v1/tasks`), so durable history stays readable when the current Active
  is unusable; an A→B Active rename leaves identity, scope and search results
  byte-identical (proven against a real managed-configuration assembly).
- **Complete find/inspect journey.** `操作与任务` landing: summary cards whose
  click applies the same server-side status filter, compact search/status/kind/
  time filters, full-width table, closed-detail default entry, mouse/keyboard
  selection opening the run overview (bounded durable facts, pause-request vs
  acknowledged state, honest item counts that never claim organize success),
  deep-link `?run=` selection, narrow-screen complete detail with an
  accessible close, and preserved Task/Job/Automation/Notification/Scan/Preview
  journeys plus workspace links. `/operations` search allowlist carries only
  bounded filters, the selection and the scope pair through auth
  continuation.
- **Honest states.** No-work/no-match/loading/read-failure/malformed/401/403
  are distinct bounded states; a failed read never renders as zero runs;
  unavailable is not zero. Strict fail-closed frontend models (attention facet
  must match the modelled status set; contradictory progress is malformed).
  Bounded polling: refetch only while a listed run is non-terminal, pause when
  the page is hidden, back off after failure, settle on terminal — and every
  poll is a GET that replays no command (browser-proven).
- **No new authority/side effects.** READ-gated endpoints that admit nothing,
  invoke no Provider and touch no Storage; zero display backfills; RecognitionType
  C and existing control/mutation rules untouched (affected suites pass).

### Tests and Results

Focused Python (exact commands from Required Tests, all PASS):

```text
.venv/bin/python -m unittest discover -s tests -p test_operations_run_inventory.py   → Ran 27, OK (new)
.venv/bin/python -m unittest discover -s tests -p test_operations_workspace.py       → Ran 20, OK
.venv/bin/python -m unittest discover -s tests -p test_task_persistence.py           → Ran 13, OK
.venv/bin/python -m unittest discover -s tests -p test_processing_worker_readiness.py → Ran 19, OK
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py         → Ran 37, OK
.venv/bin/python -m unittest discover -s tests -p test_direct_file_operations.py     → Ran 55, OK
.venv/bin/python -m unittest discover -s tests -p test_direct_file_transfers.py      → Ran 99, OK
.venv/bin/python -m unittest discover -s tests -p test_api_security.py               → Ran 13, OK
```

T4 full regression and quality/safety gates:

```text
python3 scripts/check_governance.py                                  → governance check: PASS
.venv/bin/python -m unittest discover -s tests                       → Ran 2042, OK (skipped=7)
.venv/bin/ruff format --check .                                      → 310 files already formatted
.venv/bin/ruff check .                                               → All checks passed!
.venv/bin/python -m compileall -q mediaflow tests scripts            → OK
.venv/bin/python -m pip check                                        → No broken requirements found
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate            → OK
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate → OK
git diff --check                                                     → clean
git diff --check f1806d3a13c0ab0538c07749ff82621782d91a24            → clean
sha256sum docs/pics/操作与任务.png                                    → a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86 (matches reference)
git check-ignore config/alist.json                                   → ignored; git ls-files → untracked
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml                   → UNAVAILABLE (rg not installed in this environment, exit 127);
                                                                       equivalent `grep -rniE 'ffprobe|ffmpeg' mediaflow pyproject.toml` → no matches (exit 1, the required result)
```

The 7 skips are all pre-existing environment-conditional acceptance tests
(real SMB/S3/OpenList/endurance profiles, POSIX lease, symlink availability,
container-deployment Docker gating); this Task's new suite adds zero skips.

Packaging/static-serving and migration gates:

```text
.venv/bin/python -m unittest discover -s tests -p test_release_security.py    → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_release_validation.py   → Ran 3, OK
.venv/bin/python -m unittest discover -s tests -p test_migration_rehearsal.py  → Ran 6, OK
.venv/bin/python -m unittest discover -s tests -p test_upgrade_preflight.py    → Ran 4, OK
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-wheel-AmDS → mediaflow-2.0.0.dev0-py3-none-any.whl
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-AmDS/mediaflow-2.0.0.dev0-py3-none-any.whl → PASS (runtime schema 40)
scripts/docker_release_security_smoke_test.py                        → UNAVAILABLE (environmental): the Docker daemon in this
                                                                       sandbox cannot see /tmp — a plain bind-mount probe
                                                                       (`docker run --rm -v /tmp/mount-probe:/probe alpine cat /probe/probe.txt`)
                                                                       fails "No such file or directory", so the compose stack's
                                                                       bind mounts can never resolve here, independent of repository content
```

Web (from `web/`):

```text
npm run test -- --run src/entities/operations src/features/operations src/shared/api src/routes → 29 files, 440 tests, 0 failed
npm run test -- --run                        → 57 files, 855 tests, 0 failed
npm run typecheck                            → PASS
npm run lint                                 → PASS
npm run format:check                         → PASS
npm run build                                → PASS
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts
                                             → 57 passed, 2 failed (see Risks: FAIL / PRE-EXISTING / UNRELATED)
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts → 5 passed
```

Real Python-backed browser evidence (exact reproducible command above): the
harness starts the packaged `MediaFlowApi` (which also serves the built
`/ui-v2` artifact) over one temporary SQLite database and seeds runs through
real producers (API `POST /api/v1/jobs` admission, the production
`PersistentTaskCoordinator`, the scheduler's `admit_job`); the spec then proves
real `AutomationWorker` claim→Task linkage with a stable run count and
preserved admission identity, server-side filtered selection/return,
Worker-waiting (`no_worker`) before registration, durable identity across a
real database+API restart, and GET-only side-effect-free reads.

Full fake-path e2e sweep (`npx playwright test` from `web/`): 195 passed,
31 failed — the failure set is byte-identical to Task Base (verified by
`diff` of sorted failing-test lists against a baseline run with all Task
changes stashed and a fresh baseline build): 28 storage-management, 2
deep-link, 1 dashboard. See Risks.

### Decisions

1. **Population/identity:** runs = `automation_jobs ∪ standalone tasks`,
   joined only by persisted `task_id`; a linked run keeps the admission
   (Job) identity, so an admission keeps its visible identity after acquiring
   a Task and linkage never changes the run count (browser-proven).
2. **Aggregate status** is derived in SQL with the exact precedence of
   `derive_run_status` (paused Task wins; live evidence beats terminal
   claims; terminal prefers the Task; missing evidence is `unknown`, never
   optimistic), so the page and the status partitions share one read basis.
3. **Scope evidence:** `task.scope_path` first, then the Job's recorded
   admission scope; never the current Active; published only as a bounded
   relative identity; legacy `null` stays explicitly unavailable.
4. **Cursors** use a new scoped kind `operations_runs`: every cursor binds
   the full filter state and the reading principal's ID (digested, never
   exposed); mismatched filter or principal refuses with `invalid_request`
   (read recovery), and equal-timestamp ties page deterministically by ID.
5. **Durable reads vs Active:** `/api/v1/operations/runs` is exempt from the
   Active binding refresh (same class as `/api/v1/tasks`), because it
   resolves configuration nowhere — history stays readable without a usable
   current Active.
6. **Schema 40** records the additive read indexes; the six runtime-schema
   pins were updated in the same checkpoint following the documented 38→39
   precedent (commit 2f25385). The `tasks(scope_path)` index is created after
   the additive column migration so legacy tables receive the column first.
7. **Polling** is bounded to active work: refetch every 5s only while a
   non-terminal run is listed, pause on hidden pages, settle on terminal
   states, stop after failure — GET-only, never a command replay.
8. **Intentional presentation adaptations** to existing browser journeys
   (Chinese landing labels 手动操作/任务列表/作业列表/发起受限扫描/…, scope
   selector restored on the landing) preserve every safety assertion: no
   manual action before an exact scope, exactly-one POST controls,
   resume-exactly-once, hostile-evidence rejection, read-only principals get
   no actionable control.
9. **TASK.md gates block:** added the two exact command strings required by
   `tests/test_release_security.py` (`python3 scripts/check_governance.py`,
   `scripts/docker_release_security_smoke_test.py`) — factual gate
   documentation; Goal, Scope and Acceptance Criteria unchanged.
10. **Python browser harness:** the WSGI app is `MediaFlowApi` itself (it
    serves `/ui-v2` statics and `/api/v1`), with two test-only control routes
    (`/__harness__/run-worker`, `/__harness__/restart`) as harness
    infrastructure; no product endpoint or document was added for them.

### Remaining In-Slice Work

RO-3 detail/records/export, RO-4 contextual organize entry, RO-5 queued Web continuation and RO-6
native item/batch recovery remain open. B reevaluates every RO-1–RO-7 after actual Task PASS; this
statement neither closes any Required Outcome nor authorizes another Task.

### Risks / Deviations

- **FAIL / PRE-EXISTING / UNRELATED:** 31 failures in the full fake-path e2e
  sweep (28 `storage-management`, 2 `deep-link`: "an explicit route choice at
  the boundary replaces an earlier intention" and "V1 handoff does not leak
  the token into URL or persistent stores", 1 `dashboard`: "review and
  configuration destinations remain migration placeholders"). Reproduced
  identically at Task Base with all Task changes stashed and a clean baseline
  build; failing-test sets are byte-identical (`diff` clean). Evidence kept;
  not fixed because they lie outside this Task's scope — B decides.
- **UNAVAILABLE (environmental):** `scripts/docker_release_security_smoke_test.py`
  cannot run here — the Docker daemon does not share this sandbox's `/tmp`
  (plain bind-mount probe fails), so its compose bind mounts can never
  resolve. Not caused by repository content.
- **Tool substitution:** `rg` is not installed in this environment; the
  forbidden-dependency gate was executed with the equivalent `grep -rniE`
  scan, which returned the required no-matches result.
- Run-level target scope is explicitly unavailable in this Task (Non-goal:
  per-item destination evidence stays on the existing detail surfaces);
  historical context beyond durable admission rows is deferred to RO-3.
- Pre-existing untracked `docs/pics/媒体库.png`, `docs/pics/自动化-全局设置.png`
  and `docs/pics/自动化.png` were preserved untouched and excluded from this
  Task's checkpoint.
- B's 20-test planning baseline was exceeded by the actual feature evidence
  above; no Contract ambiguity or rescope blocker was found during
  implementation.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: e89db7cff91febe8dfa220343796b367664082be
```

## B Review Result

```text
Reviewed: NOT REVIEWED
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

Fixes remain in this Task with Task ID, Task Base and Goal unchanged. FIX REQUIRED lists only
evidenced current-Contract P0/P1 blockers. If fixes exceed three rounds, B reassesses the entire
approach against actual feature need before another round; a material Contract issue returns to A.
This Task does not close the Slice or update Roadmap.
